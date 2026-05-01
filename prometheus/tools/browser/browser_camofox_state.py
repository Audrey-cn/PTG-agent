"""Prometheus-managed Camofox state helpers."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from prometheus.constants_core import get_prometheus_home

if TYPE_CHECKING:
    from pathlib import Path

CAMOFOX_STATE_DIR_NAME = "browser_auth"
CAMOFOX_STATE_SUBDIR = "camofox"


def get_camofox_state_dir() -> Path:
    """Return the profile-scoped root directory for Camofox persistence."""
    return get_prometheus_home() / CAMOFOX_STATE_DIR_NAME / CAMOFOX_STATE_SUBDIR


def get_camofox_identity(task_id: str | None = None) -> dict[str, str]:
    """Return the stable Prometheus-managed Camofox identity for this profile.

    The user identity is profile-scoped (same Prometheus profile = same userId).
    The session key is scoped to the logical browser task so newly created
    tabs within the same profile reuse the same identity contract.
    """
    scope_root = str(get_camofox_state_dir())
    logical_scope = task_id or "default"
    user_digest = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"camofox-user:{scope_root}",
    ).hex[:10]
    session_digest = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"camofox-session:{scope_root}:{logical_scope}",
    ).hex[:16]
    return {
        "user_id": f"prometheus_{user_digest}",
        "session_key": f"task_{session_digest}",
    }
