"""Shared helpers for direct xAI HTTP integrations."""

from __future__ import annotations


def prometheus_xai_user_agent() -> str:
    """Return a stable Prometheus-specific User-Agent for xAI HTTP calls."""
    try:
        from prometheus.cli import __version__
    except Exception:
        __version__ = "unknown"
    return f"Prometheus-Agent/{__version__}"
