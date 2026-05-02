"""Singularity execution environment — stub (not installed)."""

from __future__ import annotations

import logging
from typing import Any

from .base import ExecutionEnvironment, ExecutionResult

logger = logging.getLogger(__name__)


def _get_scratch_dir():
    """Return the scratch directory for singularity containers."""
    return None


class SingularityEnvironment(ExecutionEnvironment):
    """Singularity container execution environment (stub)."""

    name = "singularity"
    supports_streaming = False
    supports_cancel = False

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._image = self._config.get("image", "python:3.11.sif")

    def is_available(self) -> bool:
        """Singularity is not installed by default."""
        return False

    def execute(
        self,
        command: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> ExecutionResult:
        """Execute a command in Singularity (stub)."""
        return ExecutionResult(
            success=False,
            error="Singularity is not installed.",
            exit_code=-1,
            duration_ms=0,
        )
