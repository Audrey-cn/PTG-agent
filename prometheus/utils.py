"""Utility functions for Prometheus."""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def safe_json_loads(text: str, default: Any = None) -> Any:
    """Parse JSON, returning *default* on any parse error."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return default


def is_truthy_value(value) -> bool:
    """Check if a value is truthy.

    Handles string values like "true", "yes", "1", etc.

    Args:
        value: The value to check.

    Returns:
        True if the value is truthy, False otherwise.
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "yes", "1", "on")
    return bool(value)


def base_url_hostname(base_url: str) -> str:
    """Extract hostname from a base URL.

    Args:
        base_url: The URL to parse.

    Returns:
        The hostname string, or empty string on failure.
    """
    try:
        parsed = urlparse(base_url)
        return parsed.hostname or ""
    except Exception:
        return ""


def base_url_host_matches(base_url: str, pattern: str) -> bool:
    """Check if the hostname of base_url ends with pattern.

    Args:
        base_url: The URL to check.
        pattern: The suffix pattern to match (e.g. "amazonaws.com").

    Returns:
        True if the hostname ends with the pattern, False otherwise.
    """
    hostname = base_url_hostname(base_url)
    if not hostname:
        return False
    return hostname.endswith(pattern)


def normalize_proxy_env_vars() -> None:
    """Normalize proxy environment variables by stripping trailing slashes.

    Called before accessing HTTPS_PROXY/HTTP_PROXY/ALL_PROXY to ensure
    consistent URL formatting across different providers.
    """
    for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "https_proxy", "http_proxy", "all_proxy"):
        value = os.environ.get(key)
        if value and isinstance(value, str):
            os.environ[key] = value.rstrip("/")


def atomic_json_write(data: dict, path: Path) -> None:
    """Write JSON to a file atomically.

    Writes to a temporary file first, then renames to the target path.
    Prevents partial files if the program is interrupted mid-write.

    Args:
        data: The data to write as JSON.
        path: The target file path.
    """
    temp_path = Path(tempfile.mktemp(suffix=".json.tmp", dir=path.parent))
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
    except Exception:
        with contextlib.suppress(Exception):
            temp_path.unlink(missing_ok=True)
        raise
