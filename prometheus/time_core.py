"""Timezone-aware clock for Prometheus."""

import logging
import os
from datetime import datetime

from prometheus.constants_core import get_config_path

logger = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

_cached_tz: ZoneInfo | None = None
_cached_tz_name: str | None = None
_cache_resolved: bool = False


def _resolve_timezone_name() -> str:
    """Read the configured IANA timezone string (or empty string).

    This does file I/O when falling through to config.yaml, so callers
    should cache the result rather than calling on every ``now()``.
    """
    tz_env = os.getenv("PROMETHEUS_TIMEZONE", "").strip()
    if tz_env:
        return tz_env

    try:
        import yaml

        config_path = get_config_path()
        if config_path.exists():
            with open(config_path) as f:
                cfg = yaml.safe_load(f) or {}
            tz_cfg = cfg.get("timezone", "")
            if isinstance(tz_cfg, str) and tz_cfg.strip():
                return tz_cfg.strip()
    except Exception:
        pass

    return ""


def _get_zoneinfo(name: str) -> ZoneInfo | None:
    """Validate and return a ZoneInfo, or None if invalid."""
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except (KeyError, Exception) as exc:
        logger.warning(
            "Invalid timezone '%s': %s. Falling back to server local time.",
            name,
            exc,
        )
        return None


def get_timezone() -> ZoneInfo | None:
    """Return the user's configured ZoneInfo, or None (meaning server-local).

    Resolved once and cached. Call ``reset_cache()`` after config changes.
    """
    global _cached_tz, _cached_tz_name, _cache_resolved
    if not _cache_resolved:
        _cached_tz_name = _resolve_timezone_name()
        _cached_tz = _get_zoneinfo(_cached_tz_name)
        _cache_resolved = True
    return _cached_tz


def now() -> datetime:
    """
    Return the current time as a timezone-aware datetime.

    If a valid timezone is configured, returns wall-clock time in that zone.
    Otherwise returns the server's local time (via ``astimezone()``).
    """
    tz = get_timezone()
    if tz is not None:
        return datetime.now(tz)
    return datetime.now().astimezone()


def reset_cache() -> None:
    """Reset the timezone cache to force re-resolution on next call."""
    global _cached_tz, _cached_tz_name, _cache_resolved
    _cached_tz = None
    _cached_tz_name = None
    _cache_resolved = False
