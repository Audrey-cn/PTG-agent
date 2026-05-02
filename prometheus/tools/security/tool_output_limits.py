"""Configurable tool-output truncation limits."""

from __future__ import annotations

from typing import Any

DEFAULT_MAX_BYTES = 50_000
DEFAULT_MAX_LINES = 2000
DEFAULT_MAX_LINE_LENGTH = 2000


def _coerce_positive_int(value: Any, default: int) -> int:
    try:
        iv = int(value)
    except (TypeError, ValueError):
        return default
    if iv <= 0:
        return default
    return iv


def get_tool_output_limits() -> dict[str, int]:
    try:
        from prometheus.config import PrometheusConfig

        cfg = PrometheusConfig.load()
        section = cfg.get("tool_output") if isinstance(cfg, dict) else None
        if not isinstance(section, dict):
            section = {}
    except Exception:
        section = {}

    return {
        "max_bytes": _coerce_positive_int(section.get("max_bytes"), DEFAULT_MAX_BYTES),
        "max_lines": _coerce_positive_int(section.get("max_lines"), DEFAULT_MAX_LINES),
        "max_line_length": _coerce_positive_int(
            section.get("max_line_length"), DEFAULT_MAX_LINE_LENGTH
        ),
    }


def get_max_bytes() -> int:
    return get_tool_output_limits()["max_bytes"]


def get_max_lines() -> int:
    return get_tool_output_limits()["max_lines"]


def get_max_line_length() -> int:
    return get_tool_output_limits()["max_line_length"]
