"""Daytona environment execution backend."""

import logging
import subprocess
import time
from typing import Any

from prometheus.tools.environments.base import ExecutionEnvironment, ExecutionResult

logger = logging.getLogger(__name__)


class DaytonaEnvironment(ExecutionEnvironment):
    """
    Daytona environment for executing code in a Daytona devcontainer.

    Daytona (https://daytona.io) provides fast, reproducible development
    environments that can be used for safe code execution.
    """

    name = "daytona"
    supports_streaming = True
    supports_cancel = True

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._container_name = self._config.get("container_name", "prometheus-daytona")
        self._workspace = self._config.get("workspace", "default")
        self._image = self._config.get("image", None)

    def is_available(self) -> bool:
        """Check if Daytona CLI is available and configured."""
        try:
            result = subprocess.run(
                ["daytona", "--version"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def execute(
        self,
        command: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> ExecutionResult:
        """
        Execute a command in a Daytona workspace.

        Args:
            command: Command to execute
            args: Command arguments
            cwd: Working directory within the workspace
            env: Environment variables
            timeout: Execution timeout

        Returns:
            ExecutionResult with command output
        """
        start_time = time.time()

        cmd_args = args or []
        full_cmd = [command] + cmd_args

        daytona_cmd = ["daytona", "exec", "-w", self._workspace]

        if cwd:
            daytona_cmd.extend(["-d", cwd])

        if self._container_name:
            daytona_cmd.extend(["-c", self._container_name])

        daytona_cmd.extend(["--", "bash", "-c", " ".join(full_cmd)])

        logger.debug(f"Executing in Daytona: {' '.join(daytona_cmd)}")

        try:
            proc = subprocess.run(
                daytona_cmd, capture_output=True, text=True, timeout=timeout, env=env
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
                error="Daytona CLI not found. Install from https://daytona.io",
                exit_code=-1,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Daytona execution failed: {e}")
            return ExecutionResult(
                success=False, error=str(e), exit_code=-1, duration_ms=duration_ms
            )

    def create_workspace(self, name: str) -> bool:
        """
        Create a new Daytona workspace.

        Args:
            name: Workspace name

        Returns:
            True if successful
        """
        try:
            cmd = ["daytona", "create", name]
            if self._image:
                cmd.extend(["--image", self._image])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to create Daytona workspace {name}: {e}")
            return False

    def delete_workspace(self, name: str) -> bool:
        """
        Delete a Daytona workspace.

        Args:
            name: Workspace name

        Returns:
            True if successful
        """
        try:
            result = subprocess.run(
                ["daytona", "delete", name, "-f"], capture_output=True, text=True, timeout=60
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to delete Daytona workspace {name}: {e}")
            return False

    def list_workspaces(self) -> list[dict[str, str]]:
        """
        List all available Daytona workspaces.

        Returns:
            List of workspace info dictionaries
        """
        try:
            result = subprocess.run(
                ["daytona", "list", "-o", "json"], capture_output=True, text=True, timeout=30
            )

            if result.returncode != 0:
                return []

            import json

            return json.loads(result.stdout)
        except Exception as e:
            logger.error(f"Failed to list Daytona workspaces: {e}")
            return []
