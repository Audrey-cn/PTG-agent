"""
Simplified configuration management for Prometheus.
"""

import copy
import logging
import os
import re
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

import yaml

logger = logging.getLogger(__name__)

_IS_WINDOWS = False  # Simplified - assume non-Windows
_ENV_VAR_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_LAST_EXPANDED_CONFIG_BY_PATH: Dict[str, Any] = {}
_LOAD_CONFIG_CACHE: Dict[str, Tuple[int, int, Dict[str, Any]]] = {}


def get_prometheus_home() -> Path:
    """Get the Prometheus home directory."""
    return Path.home() / ".prometheus"


def get_config_path() -> Path:
    """Get the main config file path."""
    return get_prometheus_home() / "config.yaml"


def get_env_path() -> Path:
    """Get the .env file path (for API keys)."""
    return get_prometheus_home() / ".env"


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load config from disk."""
    if path is None:
        path = get_config_path()
    
    if not path.exists():
        return {}
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"Failed to load config: {e}")
        return {}


def save_config(config: Dict[str, Any], path: Optional[Path] = None) -> None:
    """Save config to disk."""
    if path is None:
        path = get_config_path()
    
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)


def get_config_value(key: str, default: Any = None) -> Any:
    """Get a config value by dotted key."""
    config = load_config()
    keys = key.split('.')
    value = config
    for k in keys:
        if isinstance(value, dict):
            value = value.get(k)
        else:
            return default
    return value if value is not None else default
