"""Remote model catalog fetcher."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any

from prometheus import __version__ as _PROMETHEUS_VERSION
from prometheus.utils import atomic_replace

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_CATALOG_URL = "https://prometheus-agent.nousresearch.com/docs/api/model-catalog.json"
DEFAULT_TTL_HOURS = 24
DEFAULT_FETCH_TIMEOUT = 8.0
SUPPORTED_SCHEMA_VERSION = 1

_PROMETHEUS_USER_AGENT = f"prometheus-cli/{_PROMETHEUS_VERSION}"

_catalog_cache: Dict[str, Any] | None = None
_catalog_cache_source_mtime: float = 0.0


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def _load_catalog_config() -> Dict[str, Any]:
    """Load the ``model_catalog`` config block with defaults filled in."""
    try:
        from prometheus.cli.config import load_config

        cfg = load_config() or {}
    except Exception:
        cfg = {}

    raw = cfg.get("model_catalog")
    if not isinstance(raw, dict):
        raw = {}

    return {
        "enabled": bool(raw.get("enabled", True)),
        "url": str(raw.get("url") or DEFAULT_CATALOG_URL),
        "ttl_hours": float(raw.get("ttl_hours") or DEFAULT_TTL_HOURS),
        "providers": raw.get("providers") if isinstance(raw.get("providers"), dict) else {},
    }


def _cache_path() -> Path:
    """Return the disk cache path."""
    from prometheus.constants_core import get_prometheus_home

    return get_prometheus_home() / "cache" / "model_catalog.json"


# ---------------------------------------------------------------------------
# Fetch + validate + cache
# ---------------------------------------------------------------------------


def _fetch_manifest(url: str, timeout: float) -> Dict[str, Any] | None:
    """HTTP GET the manifest URL and return a parsed dict, or None on failure."""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": _PROMETHEUS_USER_AGENT,
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        logger.info("model catalog fetch failed (%s): %s", url, exc)
        return None
    except Exception as exc:
        logger.info("model catalog fetch errored (%s): %s", url, exc)
        return None

    if not _validate_manifest(data):
        logger.info("model catalog at %s failed schema validation", url)
        return None

    return data


def _validate_manifest(data: Any) -> bool:
    """Return True when ``data`` matches the minimum manifest shape."""
    if not isinstance(data, dict):
        return False
    version = data.get("version")
    if not isinstance(version, int) or version > SUPPORTED_SCHEMA_VERSION:
        return False
    providers = data.get("providers")
    if not isinstance(providers, dict):
        return False
    for pname, pblock in providers.items():
        if not isinstance(pname, str) or not isinstance(pblock, dict):
            return False
        models = pblock.get("models")
        if not isinstance(models, list):
            return False
        for m in models:
            if not isinstance(m, dict):
                return False
            if not isinstance(m.get("id"), str) or not m["id"].strip():
                return False
    return True


def _read_disk_cache() -> Tuple[Dict[str, Any] | None, float]:
    """Return ``(data_or_none, mtime)``. mtime is 0 if file is missing."""
    path = _cache_path()
    try:
        mtime = path.stat().st_mtime
    except (OSError, FileNotFoundError):
        return (None, 0.0)
    try:
        with open(path) as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return (None, 0.0)
    if not _validate_manifest(data):
        return (None, 0.0)
    return (data, mtime)


def _write_disk_cache(data: Dict[str, Any]) -> None:
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
        atomic_replace(tmp, path)
    except OSError as exc:
        logger.info("model catalog cache write failed: %s", exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_catalog(*, force_refresh: bool = False) -> Dict[str, Any]:
    """Return the parsed model catalog manifest, or an empty dict on failure."""
    global _catalog_cache, _catalog_cache_source_mtime

    cfg = _load_catalog_config()
    if not cfg["enabled"]:
        return {}

    ttl_seconds = max(0.0, cfg["ttl_hours"] * 3600.0)

    disk_data, disk_mtime = _read_disk_cache()
    now = time.time()
    disk_fresh = disk_data is not None and (now - disk_mtime) < ttl_seconds

    if (
        not force_refresh
        and _catalog_cache is not None
        and disk_data is not None
        and disk_mtime == _catalog_cache_source_mtime
        and disk_fresh
    ):
        return _catalog_cache

    if not force_refresh and disk_fresh and disk_data is not None:
        _catalog_cache = disk_data
        _catalog_cache_source_mtime = disk_mtime
        return disk_data

    fetched = _fetch_manifest(cfg["url"], DEFAULT_FETCH_TIMEOUT)
    if fetched is not None:
        _write_disk_cache(fetched)
        new_disk_data, new_mtime = _read_disk_cache()
        if new_disk_data is not None:
            _catalog_cache = new_disk_data
            _catalog_cache_source_mtime = new_mtime
            return new_disk_data
        _catalog_cache = fetched
        _catalog_cache_source_mtime = now
        return fetched

    if disk_data is not None:
        _catalog_cache = disk_data
        _catalog_cache_source_mtime = disk_mtime
        return disk_data

    return {}


def _fetch_provider_override(provider: str) -> Dict[str, Any] | None:
    """If ``model_catalog.providers.<name>.url`` is set, fetch that instead."""
    cfg = _load_catalog_config()
    if not cfg["enabled"]:
        return None
    provider_cfg = cfg["providers"].get(provider)
    if not isinstance(provider_cfg, dict):
        return None
    override_url = provider_cfg.get("url")
    if not isinstance(override_url, str) or not override_url.strip():
        return None
    return _fetch_manifest(override_url.strip(), DEFAULT_FETCH_TIMEOUT)


def _get_provider_block(provider: str) -> Dict[str, Any] | None:
    """Return the provider's manifest block, respecting per-provider overrides."""
    override = _fetch_provider_override(provider)
    if override is not None:
        block = override.get("providers", {}).get(provider)
        if isinstance(block, dict):
            return block

    catalog = get_catalog()
    if not catalog:
        return None
    block = catalog.get("providers", {}).get(provider)
    return block if isinstance(block, dict) else None


def get_curated_openrouter_models() -> list[Tuple[str, str]] | None:
    """Return OpenRouter's curated ``[(id, description), ...]`` from the manifest."""
    block = _get_provider_block("openrouter")
    if not block:
        return None
    out: list[Tuple[str, str]] = []
    for m in block.get("models", []):
        mid = str(m.get("id") or "").strip()
        if not mid:
            continue
        desc = str(m.get("description") or "")
        out.append((mid, desc))
    return out or None


def get_curated_nous_models() -> List[str] | None:
    """Return Nous Portal's curated list of model ids from the manifest."""
    block = _get_provider_block("nous")
    if not block:
        return None
    out: List[str] = []
    for m in block.get("models", []):
        mid = str(m.get("id") or "").strip()
        if mid:
            out.append(mid)
    return out or None


def reset_cache() -> None:
    """Clear the in-process cache. Used by tests and ``prometheus model --refresh``."""
    global _catalog_cache, _catalog_cache_source_mtime
    _catalog_cache = None
    _catalog_cache_source_mtime = 0.0
