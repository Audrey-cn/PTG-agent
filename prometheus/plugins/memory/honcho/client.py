"""Honcho client initialization and configuration."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from prometheus.constants_core import get_prometheus_home

if TYPE_CHECKING:
    from honcho import Honcho

logger = logging.getLogger(__name__)

HOST = "prometheus"


def resolve_active_host() -> str:
    """Derive the Honcho host key from the active Prometheus profile.

    Resolution order:
      1. PROMETHEUS_HONCHO_HOST env var (explicit override)
      2. Active profile name via profiles system -> ``prometheus.<profile>``
      3. Fallback: ``"prometheus"`` (default profile)
    """
    explicit = os.environ.get("PROMETHEUS_HONCHO_HOST", "").strip()
    if explicit:
        return explicit

    try:
        from prometheus.cli.profiles import get_active_profile_name

        profile = get_active_profile_name()
        if profile and profile not in ("default", "custom"):
            return f"{HOST}.{profile}"
    except Exception:
        pass
    return HOST


def resolve_global_config_path() -> Path:
    """Return the shared Honcho config path for the current HOME."""
    return Path.home() / ".honcho" / "config.json"


def resolve_config_path() -> Path:
    """Return the active Honcho config path.

    Resolution order:
      1. $PROMETHEUS_HOME/honcho.json      (profile-local, if it exists)
      2. ~/.prometheus/honcho.json          (default profile — shared host blocks live here)
      3. ~/.honcho/config.json              (global, cross-app interop)

    Returns the global path if none exist (for first-time setup writes).
    """
    local_path = get_prometheus_home() / "honcho.json"
    if local_path.exists():
        return local_path

    default_path = Path.home() / ".prometheus" / "honcho.json"
    if default_path != local_path and default_path.exists():
        return default_path

    return resolve_global_config_path()


_RECALL_MODE_ALIASES = {"auto": "hybrid"}
_VALID_RECALL_MODES = {"hybrid", "context", "tools"}


def _normalize_recall_mode(val: str) -> str:
    """Normalize legacy recall mode values (e.g. 'auto' → 'hybrid')."""
    val = _RECALL_MODE_ALIASES.get(val, val)
    return val if val in _VALID_RECALL_MODES else "hybrid"


def _resolve_bool(host_val, root_val, *, default: bool) -> bool:
    """Resolve a bool config field: host wins, then root, then default."""
    if host_val is not None:
        return bool(host_val)
    if root_val is not None:
        return bool(root_val)
    return default


def _parse_context_tokens(host_val, root_val) -> int | None:
    """Parse contextTokens: host wins, then root, then None (uncapped)."""
    for val in (host_val, root_val):
        if val is not None:
            try:
                return int(val)
            except (ValueError, TypeError):
                pass
    return None


def _parse_dialectic_depth(host_val, root_val) -> int:
    """Parse dialecticDepth: host wins, then root, then 1. Clamped to 1-3."""
    for val in (host_val, root_val):
        if val is not None:
            try:
                return max(1, min(int(val), 3))
            except (ValueError, TypeError):
                pass
    return 1


_VALID_REASONING_LEVELS = ("minimal", "low", "medium", "high", "max")


def _parse_dialectic_depth_levels(host_val, root_val, depth: int) -> List[str] | None:
    """Parse dialecticDepthLevels: optional array of reasoning levels per pass."""
    for val in (host_val, root_val):
        if val is not None and isinstance(val, list):
            levels = [lvl if lvl in _VALID_REASONING_LEVELS else "low" for lvl in val[:depth]]
            while len(levels) < depth:
                levels.append("low")
            return levels
    return None


_DEFAULT_HTTP_TIMEOUT = 30.0


def _resolve_optional_float(*values: Any) -> float | None:
    """Return the first non-empty value coerced to a positive float."""
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if not value:
                continue
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            return parsed
    return None


_VALID_OBSERVATION_MODES = {"unified", "directional"}
_OBSERVATION_MODE_ALIASES = {"shared": "unified", "separate": "directional", "cross": "directional"}


def _normalize_observation_mode(val: str) -> str:
    """Normalize observation mode values."""
    val = _OBSERVATION_MODE_ALIASES.get(val, val)
    return val if val in _VALID_OBSERVATION_MODES else "directional"


_OBSERVATION_PRESETS = {
    "directional": {
        "user_observe_me": True,
        "user_observe_others": True,
        "ai_observe_me": True,
        "ai_observe_others": True,
    },
    "unified": {
        "user_observe_me": True,
        "user_observe_others": False,
        "ai_observe_me": False,
        "ai_observe_others": True,
    },
}


def _resolve_observation(
    mode: str,
    observation_obj: Optional[Dict],
) -> dict:
    """Resolve per-peer observation booleans."""
    preset = _OBSERVATION_PRESETS.get(mode, _OBSERVATION_PRESETS["directional"])
    if not observation_obj or not isinstance(observation_obj, dict):
        return dict(preset)

    user_block = observation_obj.get("user") or {}
    ai_block = observation_obj.get("ai") or {}

    return {
        "user_observe_me": user_block.get("observeMe", preSet["user_observe_me"]),
        "user_observe_others": user_block.get("observeOthers", preSet["user_observe_others"]),
        "ai_observe_me": ai_block.get("observeMe", preSet["ai_observe_me"]),
        "ai_observe_others": ai_block.get("observeOthers", preSet["ai_observe_others"]),
    }


@dataclass
class HonchoClientConfig:
    """Configuration for Honcho client, resolved for a specific host."""

    host: str = HOST
    workspace_id: str = "prometheus"
    api_key: Optional[str] = None
    environment: str = "production"
    base_url: Optional[str] = None
    timeout: float | None = None
    peer_name: Optional[str] = None
    ai_peer: str = "prometheus"
    pin_peer_name: bool = False
    enabled: bool = False
    save_messages: bool = True
    write_frequency: str | int = "async"
    context_tokens: Optional[int] = None
    dialectic_reasoning_level: str = "low"
    dialectic_dynamic: bool = True
    dialectic_max_chars: int = 600
    dialectic_depth: int = 1
    dialectic_depth_levels: List[str] | None = None
    reasoning_heuristic: bool = True
    reasoning_level_cap: str = "high"
    message_max_chars: int = 25000
    dialectic_max_input_chars: int = 10000
    recall_mode: str = "hybrid"
    init_on_session_start: bool = False
    observation_mode: str = "directional"
    user_observe_me: bool = True
    user_observe_others: bool = True
    ai_observe_me: bool = True
    ai_observe_others: bool = True
    session_strategy: str = "per-directory"
    session_peer_prefix: bool = False
    sessions: Dict[str, str] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)
    explicitly_configured: bool = False

    @classmethod
    def from_env(
        cls,
        workspace_id: str = "prometheus",
        host: Optional[str] = None,
    ) -> HonchoClientConfig:
        """Create config from environment variables (fallback)."""
        resolved_host = host or resolve_active_host()
        api_key = os.environ.get("HONCHO_API_KEY")
        base_url = os.environ.get("HONCHO_BASE_URL", "").strip() or None
        timeout = _resolve_optional_float(os.environ.get("HONCHO_TIMEOUT"))
        return cls(
            host=resolved_host,
            workspace_id=workspace_id,
            api_key=api_key,
            environment=os.environ.get("HONCHO_ENVIRONMENT", "production"),
            base_url=base_url,
            timeout=timeout,
            ai_peer=resolved_host,
            enabled=bool(api_key or base_url),
        )

    @classmethod
    def from_global_config(
        cls,
        host: Optional[str] = None,
        config_path: Optional[Path] = None,
    ) -> HonchoClientConfig:
        """Create config from the resolved Honcho config path."""
        resolved_host = host or resolve_active_host()
        path = config_path or resolve_config_path()
        if not path.exists():
            logger.debug("No global Honcho config at %s, falling back to env", path)
            return cls.from_env(host=resolved_host)

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read %s: %s, falling back to env", path, e)
            return cls.from_env(host=resolved_host)

        host_block = (raw.get("hosts") or {}).get(resolved_host, {})
        _explicitly_configured = bool(host_block) or raw.get("enabled") is True

        workspace = host_block.get("workspace") or raw.get("workspace") or resolved_host
        ai_peer = host_block.get("aiPeer") or raw.get("aiPeer") or resolved_host
        api_key = host_block.get("apiKey") or raw.get("apiKey") or os.environ.get("HONCHO_API_KEY")

        environment = host_block.get("environment") or raw.get("environment", "production")

        base_url = (
            raw.get("baseUrl")
            or raw.get("base_url")
            or os.environ.get("HONCHO_BASE_URL", "").strip()
            or None
        )
        timeout = _resolve_optional_float(
            raw.get("timeout"),
            raw.get("requestTimeout"),
            os.environ.get("HONCHO_TIMEOUT"),
        )

        host_enabled = host_block.get("enabled")
        root_enabled = raw.get("enabled")
        if host_enabled is not None:
            enabled = host_enabled
        elif root_enabled is not None:
            enabled = root_enabled
        else:
            enabled = bool(api_key or base_url)

        raw_wf = host_block.get("writeFrequency") or raw.get("writeFrequency") or "async"
        try:
            write_frequency: str | int = int(raw_wf)
        except (TypeError, ValueError):
            write_frequency = str(raw_wf)

        host_save = host_block.get("saveMessages")
        save_messages = host_save if host_save is not None else raw.get("saveMessages", True)

        session_strategy = host_block.get("sessionStrategy") or raw.get(
            "sessionStrategy", "per-directory"
        )
        host_prefix = host_block.get("sessionPeerPrefix")
        session_peer_prefix = (
            host_prefix if host_prefix is not None else raw.get("sessionPeerPrefix", False)
        )

        return cls(
            host=resolved_host,
            workspace_id=workspace,
            api_key=api_key,
            environment=environment,
            base_url=base_url,
            timeout=timeout,
            peer_name=host_block.get("peerName") or raw.get("peerName"),
            ai_peer=ai_peer,
            pin_peer_name=_resolve_bool(
                host_block.get("pinPeerName"),
                raw.get("pinPeerName"),
                default=False,
            ),
            enabled=enabled,
            save_messages=save_messages,
            write_frequency=write_frequency,
            context_tokens=_parse_context_tokens(
                host_block.get("contextTokens"),
                raw.get("contextTokens"),
            ),
            dialectic_reasoning_level=(
                host_block.get("dialecticReasoningLevel")
                or raw.get("dialecticReasoningLevel")
                or "low"
            ),
            dialectic_dynamic=_resolve_bool(
                host_block.get("dialecticDynamic"),
                raw.get("dialecticDynamic"),
                default=True,
            ),
            dialectic_max_chars=int(
                host_block.get("dialecticMaxChars") or raw.get("dialecticMaxChars") or 600
            ),
            dialectic_depth=_parse_dialectic_depth(
                host_block.get("dialecticDepth"),
                raw.get("dialecticDepth"),
            ),
            dialectic_depth_levels=_parse_dialectic_depth_levels(
                host_block.get("dialecticDepthLevels"),
                raw.get("dialecticDepthLevels"),
                depth=_parse_dialectic_depth(
                    host_block.get("dialecticDepth"), raw.get("dialecticDepth")
                ),
            ),
            reasoning_heuristic=_resolve_bool(
                host_block.get("reasoningHeuristic"),
                raw.get("reasoningHeuristic"),
                default=True,
            ),
            reasoning_level_cap=(
                host_block.get("reasoningLevelCap") or raw.get("reasoningLevelCap") or "high"
            ),
            message_max_chars=int(
                host_block.get("messageMaxChars") or raw.get("messageMaxChars") or 25000
            ),
            dialectic_max_input_chars=int(
                host_block.get("dialecticMaxInputChars")
                or raw.get("dialecticMaxInputChars")
                or 10000
            ),
            recall_mode=_normalize_recall_mode(
                host_block.get("recallMode") or raw.get("recallMode") or "hybrid"
            ),
            init_on_session_start=_resolve_bool(
                host_block.get("initOnSessionStart"),
                raw.get("initOnSessionStart"),
                default=False,
            ),
            observation_mode=_normalize_observation_mode(
                host_block.get("observationMode")
                or raw.get("observationMode")
                or ("unified" if _explicitly_configured else "directional")
            ),
            **_resolve_observation(
                _normalize_observation_mode(
                    host_block.get("observationMode")
                    or raw.get("observationMode")
                    or ("unified" if _explicitly_configured else "directional")
                ),
                host_block.get("observation") or raw.get("observation"),
            ),
            session_strategy=session_strategy,
            session_peer_prefix=session_peer_prefix,
            sessions=raw.get("sessions", {}),
            raw=raw,
            explicitly_configured=_explicitly_configured,
        )

    @staticmethod
    def _git_repo_name(cwd: str) -> str | None:
        """Return the git repo root directory name, or None if not in a repo."""
        import subprocess

        try:
            root = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=5,
            )
            if root.returncode == 0:
                return Path(root.stdout.strip()).name
        except (OSError, subprocess.TimeoutExpired):
            pass
        return None

    _HONCHO_SESSION_ID_MAX_LEN = 100
    _HONCHO_SESSION_ID_HASH_LEN = 8

    @classmethod
    def _enforce_session_id_limit(cls, sanitized: str, original: str) -> str:
        """Truncate a sanitized session ID to Honcho's 100-char limit."""
        max_len = cls._HONCHO_SESSION_ID_MAX_LEN
        if len(sanitized) <= max_len:
            return sanitized

        hash_len = cls._HONCHO_SESSION_ID_HASH_LEN
        digest = hashlib.sha256(original.encode("utf-8")).hexdigest()[:hash_len]
        prefix_len = max_len - hash_len - 1
        prefix = sanitized[:prefix_len].rstrip("-")
        return f"{prefix}-{digest}"

    def resolve_session_name(
        self,
        cwd: Optional[str] = None,
        session_title: Optional[str] = None,
        session_id: Optional[str] = None,
        gateway_session_key: Optional[str] = None,
    ) -> str | None:
        """Resolve Honcho session name."""
        import re

        if not cwd:
            cwd = os.getcwd()

        manual = self.sessions.get(cwd)
        if manual:
            return manual

        if session_title:
            sanitized = re.sub(r"[^a-zA-Z0-9_-]+", "-", session_title).strip("-")
            if sanitized:
                if self.session_peer_prefix and self.peer_name:
                    return f"{self.peer_name}-{sanitized}"
                return sanitized

        if gateway_session_key:
            sanitized = re.sub(r"[^a-zA-Z0-9_-]+", "-", gateway_session_key).strip("-")
            if sanitized:
                return self._enforce_session_id_limit(sanitized, gateway_session_key)

        if self.session_strategy == "per-session" and session_id:
            if self.session_peer_prefix and self.peer_name:
                return f"{self.peer_name}-{session_id}"
            return session_id

        if self.session_strategy == "per-repo":
            base = self._git_repo_name(cwd) or Path(cwd).name
            if self.session_peer_prefix and self.peer_name:
                return f"{self.peer_name}-{base}"
            return base

        if self.session_strategy in ("per-directory", "per-session"):
            base = Path(cwd).name
            if self.session_peer_prefix and self.peer_name:
                return f"{self.peer_name}-{base}"
            return base

        return self.workspace_id


_honcho_client: Honcho | None = None


def get_honcho_client(config: HonchoClientConfig | None = None) -> Honcho:
    """Get or create the Honcho client singleton."""
    global _honcho_client

    if _honcho_client is not None:
        return _honcho_client

    if config is None:
        config = HonchoClientConfig.from_global_config()

    if not config.api_key and not config.base_url:
        raise ValueError(
            "Honcho API key not found. "
            "Get your API key at https://app.honcho.dev, "
            "then run 'prometheus honcho setup' or set HONCHO_API_KEY. "
            "For local instances, set HONCHO_BASE_URL instead."
        )

    try:
        from honcho import Honcho
    except ImportError:
        raise ImportError(
            "honcho-ai is required for Honcho integration. Install it with: pip install honcho-ai"
        )

    resolved_base_url = config.base_url
    resolved_timeout = config.timeout
    if not resolved_base_url or resolved_timeout is None:
        try:
            from prometheus.config import PrometheusConfig

            prometheus_cfg = PrometheusConfig.load()
            honcho_cfg = prometheus_cfg.get("honcho", {})
            if isinstance(honcho_cfg, dict):
                if not resolved_base_url:
                    resolved_base_url = honcho_cfg.get("base_url", "").strip() or None
                if resolved_timeout is None:
                    resolved_timeout = _resolve_optional_float(
                        honcho_cfg.get("timeout"),
                        honcho_cfg.get("request_timeout"),
                    )
        except Exception:
            pass

    if resolved_timeout is None:
        resolved_timeout = _DEFAULT_HTTP_TIMEOUT

    if resolved_base_url:
        logger.info(
            "Initializing Honcho client (base_url: %s, workspace: %s)",
            resolved_base_url,
            config.workspace_id,
        )
    else:
        logger.info(
            "Initializing Honcho client (host: %s, workspace: %s)", config.host, config.workspace_id
        )

    _is_local = resolved_base_url and (
        "localhost" in resolved_base_url
        or "127.0.0.1" in resolved_base_url
        or "::1" in resolved_base_url
    )
    if _is_local:
        _raw = config.raw or {}
        _host_block = (_raw.get("hosts") or {}).get(config.host, {})
        _host_has_key = bool(_host_block.get("apiKey"))
        effective_api_key = config.api_key if _host_has_key else "local"
    else:
        effective_api_key = config.api_key

    kwargs: dict = {
        "workspace_id": config.workspace_id,
        "api_key": effective_api_key,
        "environment": config.environment,
    }
    if resolved_base_url:
        kwargs["base_url"] = resolved_base_url
    if resolved_timeout is not None:
        kwargs["timeout"] = resolved_timeout

    _honcho_client = Honcho(**kwargs)

    return _honcho_client


def reset_honcho_client() -> None:
    """Reset the Honcho client singleton (useful for testing)."""
    global _honcho_client
    _honcho_client = None
