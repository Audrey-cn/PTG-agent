"""Shared model-switching logic for CLI and gateway /model commands."""

from __future__ import annotations

import contextlib
import logging
import os
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


_NOUS_PROMETHEUS_NON_AGENTIC_RE = re.compile(
    r"(?:^|[/:])prometheus[-_ ]?[34](?:[-_.:]|$)",
    re.IGNORECASE,
)


def is_nous_prometheus_non_agentic(model_name: str) -> bool:
    """Return True if *model_name* is a real Nous Prometheus 3/4 chat model."""
    if not model_name:
        return False
    return bool(_NOUS_PROMETHEUS_NON_AGENTIC_RE.search(model_name))


def _check_prometheus_model_warning(model_name: str) -> str:
    """Return a warning string if *model_name* is a Nous Prometheus 3/4 chat model."""
    if is_nous_prometheus_non_agentic(model_name):
        return (
            "Nous Research Prometheus 3 & 4 models are NOT agentic and are not designed "
            "for use with Prometheus. They lack tool-calling capabilities."
        )
    return ""


class ModelIdentity:
    """Vendor slug and family prefix used for catalog resolution."""

    def __init__(self, vendor: str, family: str):
        self.vendor = vendor
        self.family = family


MODEL_ALIASES: Dict[str, ModelIdentity] = {
    "sonnet": ModelIdentity("anthropic", "claude-sonnet"),
    "opus": ModelIdentity("anthropic", "claude-opus"),
    "haiku": ModelIdentity("anthropic", "claude-haiku"),
    "claude": ModelIdentity("anthropic", "claude"),
    "gpt5": ModelIdentity("openai", "gpt-5"),
    "gpt": ModelIdentity("openai", "gpt"),
    "codex": ModelIdentity("openai", "codex"),
    "o3": ModelIdentity("openai", "o3"),
    "o4": ModelIdentity("openai", "o4"),
    "gemini": ModelIdentity("google", "gemini"),
    "deepseek": ModelIdentity("deepseek", "deepseek-chat"),
    "grok": ModelIdentity("x-ai", "grok"),
    "llama": ModelIdentity("meta-llama", "llama"),
    "qwen": ModelIdentity("qwen", "qwen"),
    "minimax": ModelIdentity("minimax", "minimax"),
    "nemotron": ModelIdentity("nvidia", "nemotron"),
    "kimi": ModelIdentity("moonshotai", "kimi"),
    "glm": ModelIdentity("z-ai", "glm"),
    "step": ModelIdentity("stepfun", "step"),
    "mimo": ModelIdentity("xiaomi", "mimo"),
}


class DirectAlias:
    """Exact model mapping that bypasses catalog resolution."""

    def __init__(self, model: str, provider: str, base_url: str = ""):
        self.model = model
        self.provider = provider
        self.base_url = base_url


_DIRECT_ALIASES: Dict[str, DirectAlias] = {}
DIRECT_ALIASES: Dict[str, DirectAlias] = {}


def _load_direct_aliases() -> Dict[str, DirectAlias]:
    """Load direct aliases from config.yaml ``model_aliases:`` section."""
    merged = dict(_DIRECT_ALIASES)
    try:
        from prometheus.config import PrometheusConfig

        cfg = PrometheusConfig.load()
        user_aliases = cfg.get("model_aliases")
        if isinstance(user_aliases, dict):
            for name, entry in user_aliases.items():
                if not isinstance(entry, dict):
                    continue
                model = entry.get("model", "")
                provider = entry.get("provider", "custom")
                base_url = entry.get("base_url", "")
                if model:
                    merged[name.strip().lower()] = DirectAlias(
                        model=model,
                        provider=provider,
                        base_url=base_url,
                    )
    except Exception:
        pass
    return merged


def _ensure_direct_aliases() -> None:
    """Lazy-load direct aliases on first use."""
    if not DIRECT_ALIASES:
        DIRECT_ALIASES.update(_load_direct_aliases())


@dataclass
class ModelSwitchResult:
    """Result of a model switch attempt."""

    success: bool
    new_model: str = ""
    target_provider: str = ""
    provider_changed: bool = False
    api_key: str = ""
    base_url: str = ""
    api_mode: str = ""
    error_message: str = ""
    warning_message: str = ""
    provider_label: str = ""
    resolved_via_alias: str = ""
    is_global: bool = False


def parse_model_flags(raw_args: str) -> Tuple[str, str, bool]:
    """Parse --provider and --global flags from /model command args.

    Returns (model_input, explicit_provider, is_global).
    """
    is_global = False
    explicit_provider = ""

    raw_args = re.sub(r"[\u2012\u2013\u2014\u2015](provider|global)", r"--\1", raw_args)

    if "--global" in raw_args:
        is_global = True
        raw_args = raw_args.replace("--global", "").strip()

    parts = raw_args.split()
    i = 0
    filtered: List[str] = []
    while i < len(parts):
        if parts[i] == "--provider" and i + 1 < len(parts):
            explicit_provider = parts[i + 1]
            i += 2
        else:
            filtered.append(parts[i])
            i += 1

    model_input = " ".join(filtered).strip()
    return (model_input, explicit_provider, is_global)


def _model_sort_key(model_id: str, prefix: str) -> tuple:
    """Sort key for model version preference."""
    rest = model_id[len(prefix) :]
    if rest.startswith("/"):
        rest = rest[1:]
    rest = rest.lstrip("-").strip()

    nums: list[float] = []
    suffix_buf = ""
    state = "start"
    num_buf = ""

    for ch in rest:
        if state == "start":
            if ch in "vV":
                state = "in_version"
            elif ch.isdigit():
                state = "in_version"
                num_buf += ch
            elif ch in "-_.":
                pass
            else:
                state = "in_suffix"
                suffix_buf += ch
        elif state == "in_version":
            if ch.isdigit():
                num_buf += ch
            elif ch == ".":
                if "." in num_buf:
                    with contextlib.suppress(ValueError):
                        nums.append(float(num_buf.rstrip(".")))
                    num_buf = ""
                else:
                    num_buf += ch
            elif ch in "-_.":
                if num_buf:
                    with contextlib.suppress(ValueError):
                        nums.append(float(num_buf.rstrip(".")))
                    num_buf = ""
                state = "between"
            else:
                if num_buf:
                    with contextlib.suppress(ValueError):
                        nums.append(float(num_buf.rstrip(".")))
                    num_buf = ""
                state = "in_suffix"
                suffix_buf += ch
        elif state == "between":
            if ch.isdigit():
                state = "in_version"
                num_buf = ch
            elif ch in "vV":
                state = "in_version"
            elif ch in "-_.":
                pass
            else:
                state = "in_suffix"
                suffix_buf += ch
        elif state == "in_suffix":
            suffix_buf += ch

    if num_buf and state == "in_version":
        with contextlib.suppress(ValueError):
            nums.append(float(num_buf.rstrip(".")))

    suffix = suffix_buf.lower().strip("-_.").strip()
    version_key = tuple(-n for n in nums)
    _SUFFIX_RANK = {"pro": 0, "max": 0, "plus": 0, "turbo": 0}
    suffix_rank = _SUFFIX_RANK.get(suffix, 1)

    return version_key + (suffix_rank, suffix)


def resolve_alias(
    raw_input: str,
    current_provider: str,
) -> Tuple[str, str, str] | None:
    """Resolve a short alias against the current provider's catalog."""
    key = raw_input.strip().lower()

    _ensure_direct_aliases()
    direct = DIRECT_ALIASES.get(key)
    if direct is not None:
        return (direct.provider, direct.model, key)

    for alias_name, da in DIRECT_ALIASES.items():
        if da.model.lower() == key:
            return (da.provider, da.model, alias_name)

    identity = MODEL_ALIASES.get(key)
    if identity is None:
        return None

    vendor, family = identity

    try:
        from prometheus.cli.models import CANONICAL_PROVIDERS

        catalog = CANONICAL_PROVIDERS.get(current_provider, {}).get("models", [])
    except Exception:
        catalog = []

    if not catalog:
        return None

    matches = [mid for mid in catalog if mid.lower().startswith(family.lower())]

    if not matches:
        return None

    matches.sort(key=lambda m: _model_sort_key(m, family))
    return (current_provider, matches[0], key)


def get_authenticated_provider_slugs(
    current_provider: str = "",
) -> List[str]:
    """Return slugs of providers that have credentials."""
    try:
        from prometheus.cli.models import CANONICAL_PROVIDERS
        from prometheus.cli.providers import get_provider_env_var

        authenticated = []
        for provider in CANONICAL_PROVIDERS:
            env_var = get_provider_env_var(provider)
            if env_var and os.environ.get(env_var):
                authenticated.append(provider)
        return authenticated
    except Exception:
        return []


def switch_model(
    raw_input: str,
    current_provider: str,
    current_model: str,
    current_base_url: str = "",
    current_api_key: str = "",
    is_global: bool = False,
    explicit_provider: str = "",
) -> ModelSwitchResult:
    """Core model-switching pipeline shared between CLI and gateway."""
    resolved_alias = ""
    new_model = raw_input.strip()
    target_provider = current_provider

    if explicit_provider:
        target_provider = explicit_provider
        if not new_model:
            new_model = _get_default_model_for_provider(target_provider)
            if not new_model:
                return ModelSwitchResult(
                    success=False,
                    target_provider=target_provider,
                    is_global=is_global,
                    error_message=f"No default model for provider '{target_provider}'",
                )

        alias_result = resolve_alias(new_model, target_provider)
        if alias_result is not None:
            _, new_model, resolved_alias = alias_result
    else:
        alias_result = resolve_alias(raw_input, current_provider)

        if alias_result is not None:
            target_provider, new_model, resolved_alias = alias_result
        else:
            key = raw_input.strip().lower()
            if key in MODEL_ALIASES:
                authed = get_authenticated_provider_slugs(current_provider=current_provider)
                for provider in authed or []:
                    result = resolve_alias(raw_input, provider)
                    if result is not None:
                        target_provider, new_model, resolved_alias = result
                        break
                else:
                    identity = MODEL_ALIASES[key]
                    return ModelSwitchResult(
                        success=False,
                        is_global=is_global,
                        error_message=f"Alias '{key}' maps to {identity.vendor}/{identity.family} but no matching model found.",
                    )

    provider_changed = target_provider != current_provider

    try:
        from prometheus.cli.models import CANONICAL_PROVIDERS

        provider_label = CANONICAL_PROVIDERS.get(target_provider, {}).get("label", target_provider)
    except Exception:
        provider_label = target_provider

    api_key = current_api_key
    base_url = current_base_url

    if provider_changed or explicit_provider:
        try:
            from prometheus.cli.providers import get_provider_config

            config = get_provider_config(target_provider)
            env_var = config.get("env_var", "")
            if env_var:
                api_key = os.environ.get(env_var, "")
            base_url = config.get("base_url", "")
        except Exception as e:
            return ModelSwitchResult(
                success=False,
                target_provider=target_provider,
                provider_label=provider_label,
                is_global=is_global,
                error_message=f"Could not resolve credentials: {e}",
            )
    else:
        if not api_key:
            try:
                from prometheus.cli.providers import get_provider_config

                config = get_provider_config(current_provider)
                env_var = config.get("env_var", "")
                if env_var:
                    api_key = os.environ.get(env_var, "")
            except Exception:
                pass

    if resolved_alias:
        _ensure_direct_aliases()
        _da = DIRECT_ALIASES.get(resolved_alias)
        if _da is not None and _da.base_url:
            base_url = _da.base_url
            if not api_key:
                api_key = "no-key-required"

    warnings: List[str] = []
    prometheus_warn = _check_prometheus_model_warning(new_model)
    if prometheus_warn:
        warnings.append(prometheus_warn)

    return ModelSwitchResult(
        success=True,
        new_model=new_model,
        target_provider=target_provider,
        provider_changed=provider_changed,
        api_key=api_key,
        base_url=base_url,
        warning_message=" | ".join(warnings) if warnings else "",
        provider_label=provider_label,
        resolved_via_alias=resolved_alias,
        is_global=is_global,
    )


def _get_default_model_for_provider(provider: str) -> str:
    """Get default model for a provider."""
    try:
        from prometheus.cli.models import CANONICAL_PROVIDERS

        return CANONICAL_PROVIDERS.get(provider, {}).get("default_model", "")
    except Exception:
        return ""


def list_authenticated_providers(
    current_provider: str = "",
    current_model: str = "",
    max_models: int = 8,
) -> list[dict]:
    """Detect which providers have credentials and list their curated models."""
    results: list[dict] = []
    seen_slugs: set = set()

    try:
        from prometheus.cli.models import CANONICAL_PROVIDERS
    except Exception:
        return results

    for slug, spec in CANONICAL_PROVIDERS.items():
        env_var = spec.get("env_var", "")
        has_creds = bool(env_var and os.environ.get(env_var))

        if not has_creds:
            continue

        models = spec.get("models", [])
        total = len(models)
        top = models[:max_models]

        results.append(
            {
                "slug": slug,
                "name": spec.get("label", slug),
                "is_current": slug == current_provider,
                "is_user_defined": False,
                "models": top,
                "total_models": total,
                "source": "built-in",
            }
        )
        seen_slugs.add(slug.lower())

    results.sort(key=lambda r: (not r["is_current"], -r["total_models"]))
    return results
