"""
Simplified utilities for Prometheus.
Provides helper functions needed by browser_tool and auxiliary_client.
"""

import contextlib
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def safe_json_loads(text: str, default: Any = None) -> Any:
    """Parse JSON, returning *default* on any parse error."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return default


def atomic_json_write(data: dict, path: Path) -> None:
    """Write JSON to a file atomically."""
    temp_path = Path(tempfile.mktemp(suffix=".json.tmp", dir=path.parent))
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
    except Exception:
        with contextlib.suppress(Exception):
            temp_path.unlink(missing_ok=True)
        raise


def base_url_host_matches(base_url: str, hostname: str) -> bool:
    """Check if a base URL contains the given hostname."""
    if not base_url:
        return False
    return hostname.lower() in base_url.lower()


def base_url_hostname(base_url: str) -> str:
    """Extract hostname from a base URL."""
    if not base_url:
        return ""
    try:
        parsed = urlparse(base_url)
        return parsed.hostname or ""
    except Exception:
        return ""


def normalize_proxy_env_vars() -> Dict[str, str]:
    """Normalize proxy environment variables."""
    proxies = {}
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        if key in os.environ:
            proxies[key] = os.environ[key]
    return proxies


def atomic_replace(path: Path, content: str, mode: int = 0o644) -> None:
    """Atomically write content to a file."""
    dir_path = path.parent
    dir_path.mkdir(parents=True, exist_ok=True)
    
    fd, tmp_path = tempfile.mkstemp(dir=str(dir_path))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(content)
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, str(path))
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def safe_json_dumps(obj: Any, **kwargs) -> str:
    """Safely dump object to JSON string."""
    try:
        return json.dumps(obj, ensure_ascii=False, **kwargs)
    except (TypeError, ValueError):
        return str(obj)


def is_truthy_value(value: Any) -> bool:
    """Check if a value is truthy (for config boolean detection)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("1", "true", "yes", "on")
    return bool(value)
