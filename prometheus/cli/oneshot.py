"""Oneshot (-z) mode: send a prompt, get the final content block, exit."""

from __future__ import annotations

import logging
import os
import sys
from contextlib import redirect_stderr, redirect_stdout, suppress


def _normalize_toolsets(toolsets: object = None) -> List[str] | None:
    if not toolsets:
        return None

    raw_items = [toolsets] if isinstance(toolsets, str) else toolsets
    if not isinstance(raw_items, (list, tuple)):
        raw_items = [raw_items]

    normalized: List[str] = []
    for item in raw_items:
        if isinstance(item, str):
            normalized.extend(part.strip() for part in item.split(","))
        else:
            normalized.append(str(item).strip())

    return [item for item in normalized if item] or None


def _validate_explicit_toolsets(toolsets: object = None) -> Tuple[List[str] | None, str | None]:
    normalized = _normalize_toolsets(toolsets)
    if normalized is None:
        return None, None

    try:
        from prometheus.toolsets import validate_toolset
    except Exception as exc:
        return None, f"prometheus -z: failed to validate --toolsets: {exc}\n"

    built_in = [name for name in normalized if validate_toolset(name)]
    unresolved = [name for name in normalized if name not in built_in]

    if unresolved:
        try:
            from prometheus.cli.plugins import discover_plugins

            discover_plugins()
            plugin_valid = [name for name in unresolved if validate_toolset(name)]
        except Exception:
            plugin_valid = []

        if plugin_valid:
            built_in.extend(plugin_valid)
            unresolved = [name for name in unresolved if name not in plugin_valid]

    if any(name in {"all", "*"} for name in built_in):
        ignored = [name for name in normalized if name not in {"all", "*"}]
        if ignored:
            sys.stderr.write(
                "prometheus -z: --toolsets all enables every toolset; "
                f"ignoring additional entries: {', '.join(ignored)}\n"
            )
        return None, None

    mcp_names: Set[str] = set()
    mcp_disabled: Set[str] = set()
    if unresolved:
        try:
            from prometheus.config import PrometheusConfig

            cfg = PrometheusConfig.load()
            mcp_servers = cfg.get("mcp_servers") if isinstance(cfg.get("mcp_servers"), dict) else {}
            for name, server_cfg in mcp_servers.items():
                if not isinstance(server_cfg, dict):
                    continue
                enabled = server_cfg.get("enabled", True)
                if isinstance(enabled, str):
                    enabled = enabled.lower() in ("true", "1", "yes")
                if enabled:
                    mcp_names.add(str(name))
                else:
                    mcp_disabled.add(str(name))
        except Exception:
            mcp_names = set()
            mcp_disabled = set()

    mcp_valid = [name for name in unresolved if name in mcp_names]
    disabled = [name for name in unresolved if name in mcp_disabled]
    unknown = [name for name in unresolved if name not in mcp_names and name not in mcp_disabled]
    valid = built_in + mcp_valid

    if unknown:
        sys.stderr.write(
            f"prometheus -z: ignoring unknown --toolsets entries: {', '.join(unknown)}\n"
        )
    if disabled:
        sys.stderr.write(
            "prometheus -z: ignoring disabled MCP servers (set enabled: true in config.yaml to use): "
            f"{', '.join(disabled)}\n"
        )

    if not valid:
        return None, "prometheus -z: --toolsets did not contain any valid toolsets.\n"

    return valid, None


def run_oneshot(
    prompt: str,
    model: str | None = None,
    provider: str | None = None,
    toolsets: object = None,
) -> int:
    """Execute a single prompt and print only the final content block.

    Returns the exit code. Caller should sys.exit() with the return.
    """
    logging.disable(logging.CRITICAL)

    env_model_early = os.getenv("PROMETHEUS_INFERENCE_MODEL", "").strip()
    if provider and not ((model or "").strip() or env_model_early):
        sys.stderr.write(
            "prometheus -z: --provider requires --model (or PROMETHEUS_INFERENCE_MODEL). "
            "Pass both explicitly, or neither to use your configured defaults.\n"
        )
        return 2

    explicit_toolsets, toolsets_error = _validate_explicit_toolsets(toolsets)
    if toolsets_error:
        sys.stderr.write(toolsets_error)
        return 2
    use_config_toolsets = _normalize_toolsets(toolsets) is None

    os.environ["PROMETHEUS_YOLO_MODE"] = "1"
    os.environ["PROMETHEUS_ACCEPT_HOOKS"] = "1"

    real_stdout = sys.stdout
    devnull = open(os.devnull, "w")

    try:
        with redirect_stdout(devnull), redirect_stderr(devnull):
            response = _run_agent(
                prompt,
                model=model,
                provider=provider,
                toolsets=explicit_toolsets,
                use_config_toolsets=use_config_toolsets,
            )
    finally:
        with suppress(Exception):
            devnull.close()

    if response:
        real_stdout.write(response)
        if not response.endswith("\n"):
            real_stdout.write("\n")
        real_stdout.flush()
    return 0


def _run_agent(
    prompt: str,
    model: str | None = None,
    provider: str | None = None,
    toolsets: object = None,
    use_config_toolsets: bool = True,
) -> str:
    """Build an AIAgent exactly like a normal CLI chat turn would."""
    from prometheus.agent import AIAgent
    from prometheus.cli.model_switch import switch_model
    from prometheus.config import PrometheusConfig

    cfg = PrometheusConfig.load()

    model_cfg = cfg.get("model") or {}
    if isinstance(model_cfg, str):
        cfg_model = model_cfg
    else:
        cfg_model = model_cfg.get("default") or model_cfg.get("model") or ""

    env_model = os.getenv("PROMETHEUS_INFERENCE_MODEL", "").strip()
    effective_model = (model or "").strip() or env_model or cfg_model

    effective_provider = (provider or "").strip() or None
    explicit_base_url_from_alias: str | None = None

    if effective_provider is None and (model or env_model):
        explicit_model = (model or "").strip() or env_model
        if explicit_model:
            try:
                from prometheus.cli import model_switch as _ms

                _ms._ensure_direct_aliases()
                direct = _ms.DIRECT_ALIASES.get(explicit_model.strip().lower())
            except Exception:
                direct = None
            if direct is not None:
                effective_model = direct.model
                effective_provider = direct.provider
                if direct.base_url:
                    explicit_base_url_from_alias = direct.base_url.rstrip("/")
            else:
                cfg_provider = ""
                if isinstance(model_cfg, dict):
                    cfg_provider = str(model_cfg.get("provider") or "").strip().lower()
                current_provider = (
                    cfg_provider
                    or os.getenv("PROMETHEUS_INFERENCE_PROVIDER", "").strip().lower()
                    or "auto"
                )
                result = switch_model(
                    explicit_model,
                    current_provider=current_provider,
                    current_model="",
                )
                if result.success:
                    effective_provider = result.target_provider
                    effective_model = result.new_model

    if effective_provider is None:
        effective_provider = "auto"

    runtime = _resolve_runtime_provider(
        requested=effective_provider,
        target_model=effective_model or None,
        explicit_base_url=explicit_base_url_from_alias,
    )

    toolsets_list = _normalize_toolsets(toolsets)
    if toolsets_list is None and use_config_toolsets:
        toolsets_list = sorted(_get_platform_tools(cfg, "cli"))

    agent = AIAgent(
        api_key=runtime.get("api_key"),
        base_url=runtime.get("base_url"),
        provider=runtime.get("provider"),
        api_mode=runtime.get("api_mode"),
        model=effective_model,
        enabled_toolsets=toolsets_list,
        quiet_mode=True,
        platform="cli",
        credential_pool=runtime.get("credential_pool"),
        clarify_callback=_oneshot_clarify_callback,
    )

    agent.suppress_status_output = True
    agent.stream_delta_callback = None
    agent.tool_gen_callback = None

    return agent.chat(prompt) or ""


def _resolve_runtime_provider(
    requested: str | None = None,
    target_model: str | None = None,
    explicit_base_url: str | None = None,
) -> dict:
    """Resolve runtime provider credentials."""
    from prometheus.cli.providers import get_provider_config

    result = {
        "api_key": "",
        "base_url": "",
        "provider": requested or "auto",
        "api_mode": "",
        "credential_pool": None,
    }

    if requested and requested != "auto":
        config = get_provider_config(requested)
        if config:
            env_var = config.get("env_var", "")
            if env_var:
                result["api_key"] = os.environ.get(env_var, "")
            result["base_url"] = explicit_base_url or config.get("base_url", "")

    return result


def _get_platform_tools(cfg: dict, platform: str) -> List[str]:
    """Get tools for a platform from config."""
    toolsets = cfg.get("toolsets", ["prometheus-cli"])
    if isinstance(toolsets, list):
        return toolsets
    return ["prometheus-cli"]


def _oneshot_clarify_callback(question: str, choices=None) -> str:
    """Clarify is disabled in oneshot mode."""
    if choices:
        return (
            f"[oneshot mode: no user available. Pick the best option from "
            f"{choices} using your own judgment and continue.]"
        )
    return (
        "[oneshot mode: no user available. Make the most reasonable "
        "assumption you can and continue.]"
    )
