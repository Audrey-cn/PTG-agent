"""SSH execution environment."""

import logging
import time
from typing import Any

from .base import ExecutionEnvironment, ExecutionResult

logger = logging.getLogger(__name__)


class SSHEnvironment(ExecutionEnvironment):
    """SSH remote execution environment.

    Executes commands on a remote machine via SSH.
    """

    name = "ssh"
    supports_streaming = True
    supports_cancel = True

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._host = self._config.get("host", "localhost")
        self._port = self._config.get("port", 22)
        self._user = self._config.get("user", "root")
        self._key_file = self._config.get("key_file", None)
        self._password = self._config.get("password", None)

    def is_available(self) -> bool:
        """Check if SSH is configured."""
        return bool(self._host and (self._key_file or self._password))

    def execute(
        self,
        command: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> ExecutionResult:
        """Execute a command over SSH."""
        import subprocess

        start_time = time.time()

        cmd_args = [command] + (args or [])
        full_cmd = " ".join(cmd_args)

        ssh_cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "BatchMode=yes",
        ]

        if self._port != 22:
            ssh_cmd.extend(["-p", str(self._port)])

        if self._key_file:
            ssh_cmd.extend(["-i", self._key_file])

        ssh_cmd.append(f"{self._user}@{self._host}")

        if cwd:
            full_cmd = f"cd {cwd} && {full_cmd}"

        ssh_cmd.extend(["sh", "-c", full_cmd])

        logger.debug(f"Executing over SSH: {' '.join(ssh_cmd)}")

        try:
            proc = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
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
                error="SSH not found",
                exit_code=-1,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"SSH execution failed: {e}")
            return ExecutionResult(
                success=False,
                error=str(e),
                exit_code=-1,
                duration_ms=duration_ms,
            )

    def test_connection(self) -> bool:
        """Test the SSH connection."""
        result = self.execute("echo", ["test"])
        return result.success
