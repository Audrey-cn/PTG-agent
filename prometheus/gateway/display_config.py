"""Per-platform display/verbosity configuration resolver."""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Overrideable display settings and their global defaults
# ---------------------------------------------------------------------------
# These are the settings that can be configured per-platform.
# Other display settings (compact, personality, skin, etc.) are CLI-only
# and don't participate in per-platform resolution.

_GLOBAL_DEFAULTS: Dict[str, Any] = {
    "tool_progress": "all",
    "show_reasoning": False,
    "tool_preview_length": 0,
    "streaming": None,  # None = follow top-level streaming config
}

# ---------------------------------------------------------------------------
# Sensible per-platform defaults — tiered by platform capability
# ---------------------------------------------------------------------------
# Tier 1 (high): Supports message editing, typically personal/team use
# Tier 2 (medium): Supports editing but often workspace/customer-facing
# Tier 3 (low): No edit support — each progress msg is permanent
# Tier 4 (minimal): Batch/non-interactive delivery

_TIER_HIGH = {
    "tool_progress": "all",
    "show_reasoning": False,
    "tool_preview_length": 40,
    "streaming": None,  # follow global
}

_TIER_MEDIUM = {
    "tool_progress": "new",
    "show_reasoning": False,
    "tool_preview_length": 40,
    "streaming": None,
}

_TIER_LOW = {
    "tool_progress": "off",
    "show_reasoning": False,
    "tool_preview_length": 40,
    "streaming": False,
}

_TIER_MINIMAL = {
    "tool_progress": "off",
    "show_reasoning": False,
    "tool_preview_length": 0,
    "streaming": False,
}

_PLATFORM_DEFAULTS: Dict[str, Dict[str, Any]] = {
    # Tier 1 — full edit support, personal/team use
    "telegram": _TIER_HIGH,
    "discord": _TIER_HIGH,
    # Tier 2 — edit support, often customer/workspace channels
    "slack": {**_TIER_MEDIUM, "tool_progress": "off"},
    "mattermost": _TIER_MEDIUM,
    "matrix": _TIER_MEDIUM,
    "feishu": _TIER_MEDIUM,
    # Tier 3 — no edit support, progress messages are permanent
    "signal": _TIER_LOW,
    "whatsapp": _TIER_MEDIUM,
    "bluebubbles": _TIER_LOW,
    "weixin": _TIER_LOW,
    "wecom": _TIER_LOW,
    "wecom_callback": _TIER_LOW,
    "dingtalk": _TIER_LOW,
    # Tier 4 — batch or non-interactive delivery
    "email": _TIER_MINIMAL,
    "sms": _TIER_MINIMAL,
    "webhook": _TIER_MINIMAL,
    "homeassistant": _TIER_MINIMAL,
    "api_server": {**_TIER_HIGH, "tool_preview_length": 0},
}

# Canonical set of per-platform overrideable keys (for validation).
OVERRIDEABLE_KEYS = frozenset(_GLOBAL_DEFAULTS.keys())


def resolve_display_setting(
    user_config: dict,
    platform_key: str,
    setting: str,
    fallback: Any = None,
) -> Any:
    """Resolve a display setting with per-platform override support.

    Parameters
    ----------
    user_config : dict
        Full parsed config.yaml dict.
    platform_key : str
        Platform config key (e.g. ``"telegram"``, ``"slack"``).
    setting : str
        Display setting name (e.g. ``"tool_progress"``, ``"show_reasoning"``).
    fallback : Any
        Fallback value when setting isn't found anywhere.

    Returns
    -------
    Resolved value, or *fallback* if nothing is configured.
    """
    display_cfg = user_config.get("display") or {}

    # 1. Explicit per-platform override (display.platforms.<platform>.<key>)
    platforms = display_cfg.get("platforms") or {}
    plat_overrides = platforms.get(platform_key)
    if isinstance(plat_overrides, dict):
        val = plat_overrides.get(setting)
        if val is not None:
            return _normalise(setting, val)

    # 2. Global user setting (display.<key>). Skip display.streaming because
    # it controls only CLI terminal streaming; gateway streaming is governed
    # by top-level streaming config plus per-platform overrides.
    if setting != "streaming":
        val = display_cfg.get(setting)
        if val is not None:
            return _normalise(setting, val)

    # 3. Built-in platform default
    plat_defaults = _PLATFORM_DEFAULTS.get(platform_key)
    if plat_defaults:
        val = plat_defaults.get(setting)
        if val is not None:
            return val

    # 4. Built-in global default
    val = _GLOBAL_DEFAULTS.get(setting)
    if val is not None:
        return val

    return fallback


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalise(setting: str, value: Any) -> Any:
    """Normalise YAML quirks (bare ``off`` → False in YAML 1.1)."""
    if setting == "tool_progress":
        if value is False:
            return "off"
        if value is True:
            return "all"
        return str(value).lower()
    if setting in ("show_reasoning", "streaming"):
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        return bool(value)
    if setting == "tool_preview_length":
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    return value
