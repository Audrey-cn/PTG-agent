from __future__ import annotations

import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from prometheus.config import get_prometheus_home


@dataclass
class GatewayConfig:
    host: str = "0.0.0.0"
    port: int = 8765
    enabled_platforms: list[str] = field(default_factory=lambda: ["cli"])
    debug: bool = False
    max_sessions: int = 10
    session_timeout: int = 3600


def _gateway_config_path() -> Path:
    return get_prometheus_home() / "gateway_config.yaml"


def load_gateway_config() -> GatewayConfig:
    path = _gateway_config_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return GatewayConfig(
                host=data.get("host", "0.0.0.0"),
                port=data.get("port", 8765),
                enabled_platforms=data.get("enabled_platforms", ["cli"]),
                debug=data.get("debug", False),
                max_sessions=data.get("max_sessions", 10),
                session_timeout=data.get("session_timeout", 3600),
            )
        except Exception:
            pass
    return GatewayConfig()


def save_gateway_config(config: GatewayConfig) -> None:
    path = _gateway_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "host": config.host,
        "port": config.port,
        "enabled_platforms": config.enabled_platforms,
        "debug": config.debug,
        "max_sessions": config.max_sessions,
        "session_timeout": config.session_timeout,
    }
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
