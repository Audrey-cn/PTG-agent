"""Prometheus constants stub for Prometheus."""

import os
from pathlib import Path


def get_prometheus_home() -> Path:
    """Get the Prometheus home directory."""
    return Path.home() / ".prometheus"


def get_default_prometheus_root() -> Path:
    """Get the default Prometheus root directory."""
    return get_prometheus_home()


def get_optional_skills_dir() -> Path:
    """Get the optional skills directory."""
    return get_prometheus_home() / "skills"


def is_container() -> bool:
    """Check if running in a container."""
    return os.environ.get("PROMETHEUS_CONTAINER", "").lower() in ("1", "true", "yes")


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
AI_GATEWAY_BASE_URL = "https://ai-gateway.api.nousresearch.com/v1"
