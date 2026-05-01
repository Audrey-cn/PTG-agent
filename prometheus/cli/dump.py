from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from prometheus.config import get_prometheus_home, get_config_path, PrometheusConfig


def dump_config() -> dict[str, Any]:
    config = PrometheusConfig.load()
    return config.to_dict()


def dump_env() -> dict[str, str]:
    env_vars = {}
    prometheus_vars = [
        "PROMETHEUS_HOME",
        "PROMETHEUS_CONFIG",
        "PROMETHEUS_MODEL",
        "PROMETHEUS_PROVIDER",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "AZURE_OPENAI_API_KEY",
    ]
    for var in prometheus_vars:
        value = os.environ.get(var)
        if value:
            if "KEY" in var or "SECRET" in var:
                env_vars[var] = "***REDACTED***"
            else:
                env_vars[var] = value
    return env_vars


def dump_sessions() -> dict[str, Any]:
    sessions_dir = get_prometheus_home() / "sessions"
    sessions = {}
    if sessions_dir.exists():
        for session_file in sessions_dir.glob("*.json"):
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    sessions[session_file.stem] = json.load(f)
            except Exception:
                sessions[session_file.stem] = {"error": "Failed to read session"}
    return sessions


def dump_state() -> dict[str, Any]:
    return {
        "timestamp": datetime.now().isoformat(),
        "prometheus_home": str(get_prometheus_home()),
        "config": dump_config(),
        "env": dump_env(),
        "sessions": dump_sessions(),
    }


def save_dump(path: str | Path) -> None:
    path = Path(path)
    state = dump_state()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, default=str)
