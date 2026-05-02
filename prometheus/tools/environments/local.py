"""Local execution environment."""

import logging
import subprocess
import time
from typing import Any

from .base import ExecutionEnvironment, ExecutionResult

logger = logging.getLogger(__name__)


class LocalEnvironment(ExecutionEnvironment):
    """Local machine execution environment.

    Executes commands directly on the local system.
    """

    name = "local"
    supports_streaming = True
    supports_cancel = True

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._processes: dict[str, subprocess.Popen] = {}

    def is_available(self) -> bool:
        """Local execution is always available."""
        return True

    def execute(
        self,
        command: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> ExecutionResult:
        """Execute a command locally."""
        import os
        import shlex

        start_time = time.time()

        if args:
            cmd = [command] + list(args)
        else:
            cmd = shlex.split(command)
        
        full_cmd = " ".join(cmd)

        logger.debug(f"Executing locally: {full_cmd}")

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=cwd or os.getcwd(),
                env=env or None,
                timeout=timeout,
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
                error=f"Command timed out after {timeout}s",
                exit_code=-1,
                duration_ms=duration_ms,
            )

        except FileNotFoundError:
            duration_ms = (time.time() - start_time) * 1000
            return ExecutionResult(
                success=False,
                error=f"Command not found: {command}",
                exit_code=-1,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Local execution failed: {e}")
            return ExecutionResult(
                success=False,
                error=str(e),
                exit_code=-1,
                duration_ms=duration_ms,
            )

    def execute_interactive(
        self,
        command: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> ExecutionResult:
        """Execute a command interactively."""
        import os

        cmd = [command] + (args or [])

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=cwd or os.getcwd(),
                env=env or None,
            )

            self._processes[command] = proc

            proc.wait()

            self._processes.pop(command, None)

            return ExecutionResult(
                success=proc.returncode == 0,
                exit_code=proc.returncode or 0,
            )

        except Exception as e:
            logger.error(f"Interactive execution failed: {e}")
            return ExecutionResult(
                success=False,
                error=str(e),
                exit_code=-1,
            )

    def cancel(self, session_id: str) -> bool:
        """Cancel a running process."""
        if session_id in self._processes:
            proc = self._processes[session_id]
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            del self._processes[session_id]
            return True
        return False
