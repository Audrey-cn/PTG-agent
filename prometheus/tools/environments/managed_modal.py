"""Managed Modal execution environment (stub)."""

from __future__ import annotations

import logging
from typing import Any

from .base import ExecutionEnvironment, ExecutionResult

logger = logging.getLogger(__name__)


class ManagedModalEnvironment(ExecutionEnvironment):
    """Managed Modal execution environment.

    Executes commands via the managed tool gateway on Modal.
    """

    name = "managed_modal"
    supports_streaming = True
    supports_cancel = True

    def __init__(
        self,
        image: str = "python:3.11",
        cwd: str | None = None,
        timeout: int = 300,
        modal_sandbox_kwargs: dict[str, Any] | None = None,
        persistent_filesystem: bool = False,
        task_id: str | None = None,
    ) -> None:
        super().__init__()
        self._image = image
        self._cwd = cwd
        self._timeout = timeout
        self._sandbox_kwargs = modal_sandbox_kwargs or {}
        self._persistent_filesystem = persistent_filesystem
        self._task_id = task_id

    def is_available(self) -> bool:
        """Check if managed Modal is available."""
        try:
            from prometheus.tools.managed_tool_gateway import is_managed_tool_gateway_ready
            return is_managed_tool_gateway_ready("modal")
        except Exception:
            return False

    def execute(
        self,
        command: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> ExecutionResult:
        """Execute a command via managed Modal."""
        import subprocess
        import time

        start_time = time.time()
        cmd = [command] + (args or [])
        full_cmd = " ".join(cmd)

        logger.debug(f"Executing via managed Modal: {full_cmd}")

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout or self._timeout,
                cwd=cwd or self._cwd,
                env=env,
            )

            duration_ms = (time.time() - start_time) * 1000

            return ExecutionResult(
                success=proc.returncode == 0,
                output=proc.stdout,
                error=proc.stderr,
                exit_code=proc.returncode,
                duration_ms=duration_ms,
            )

        except subprocess.TimeoutExpired:
            duration_ms = (time.time() - start_time) * 1000
            return ExecutionResult(
                success=False,
                error=f"Command timed out after {timeout or self._timeout}s",
                exit_code=-1,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Managed Modal execution failed: {e}")
            return ExecutionResult(
                success=False,
                error=str(e),
                exit_code=-1,
                duration_ms=duration_ms,
            )
