from __future__ import annotations

import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from prometheus.config import get_prometheus_home


@dataclass
class DisplayConfig:
    show_timestamps: bool = True
    show_tokens: bool = False
    show_model: bool = False
    show_latency: bool = True
    theme: str = "default"
    max_message_width: int = 80


def _display_config_path() -> Path:
    return get_prometheus_home() / "display_config.yaml"


def load_display_config() -> DisplayConfig:
    path = _display_config_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return DisplayConfig(
                show_timestamps=data.get("show_timestamps", True),
                show_tokens=data.get("show_tokens", False),
                show_model=data.get("show_model", False),
                show_latency=data.get("show_latency", True),
                theme=data.get("theme", "default"),
                max_message_width=data.get("max_message_width", 80),
            )
        except Exception:
            pass
    return DisplayConfig()


def save_display_config(config: DisplayConfig) -> None:
    path = _display_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "show_timestamps": config.show_timestamps,
        "show_tokens": config.show_tokens,
        "show_model": config.show_model,
        "show_latency": config.show_latency,
        "theme": config.theme,
        "max_message_width": config.max_message_width,
    }
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


_current_display_config: DisplayConfig | None = None


def apply_display_config(config: DisplayConfig) -> None:
    global _current_display_config
    _current_display_config = config


def get_current_display_config() -> DisplayConfig:
    global _current_display_config
    if _current_display_config is None:
        _current_display_config = load_display_config()
    return _current_display_config
