"""Modal cloud execution environment."""

import logging
import time
from typing import Any

from .base import ExecutionEnvironment, ExecutionResult

logger = logging.getLogger(__name__)


class ModalEnvironment(ExecutionEnvironment):
    """Modal cloud execution environment.

    Executes functions serverlessly on Modal.
    See https://modal.com
    """

    name = "modal"
    supports_streaming = True
    supports_cancel = True

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._app_name = self._config.get("app_name", "prometheus")
        self._image = self._config.get("image", "python:3.11")
        self._gpu = self._config.get("gpu", None)
        self._timeout = self._config.get("timeout", 300)

    def is_available(self) -> bool:
        """Check if Modal is configured."""
        try:
            import modal

            return True
        except ImportError:
            return False

    def execute(
        self,
        command: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> ExecutionResult:
        """Execute a function on Modal."""
        import subprocess

        start_time = time.time()

        cmd_args = [command] + (args or [])
        full_cmd = " ".join(cmd_args)

        modal_cmd = ["modal", "run"]

        if self._gpu:
            modal_cmd.extend(["--gpu", self._gpu])

        modal_cmd.extend(["--timeout", str(timeout or self._timeout)])
        modal_cmd.append(full_cmd)

        logger.debug(f"Executing on Modal: {' '.join(modal_cmd)}")

        try:
            proc = subprocess.run(
                modal_cmd,
                capture_output=True,
                text=True,
                timeout=timeout or self._timeout,
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

        except FileNotFoundError:
            duration_ms = (time.time() - start_time) * 1000
            return ExecutionResult(
                success=False,
                error="Modal CLI not found. Install with: pip install modal",
                exit_code=-1,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Modal execution failed: {e}")
            return ExecutionResult(
                success=False,
                error=str(e),
                exit_code=-1,
                duration_ms=duration_ms,
            )

    def deploy(self, function_code: str, function_name: str = "main") -> bool:
        """Deploy a function to Modal."""
        import subprocess

        try:
            result = subprocess.run(
                ["modal", "deploy", "--name", function_name],
                input=function_code,
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Modal deploy failed: {e}")
            return False
