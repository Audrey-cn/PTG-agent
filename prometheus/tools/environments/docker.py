"""Docker execution environment."""

import logging
import time
from typing import Any

from .base import ExecutionEnvironment, ExecutionResult

logger = logging.getLogger(__name__)


class DockerEnvironment(ExecutionEnvironment):
    """Docker container execution environment.

    Executes commands inside a Docker container.
    """

    name = "docker"
    supports_streaming = True
    supports_cancel = True

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._image = self._config.get("image", "python:3.11-slim")
        self._container_name = self._config.get("container_name", None)
        self._network = self._config.get("network", None)
        self._volumes = self._config.get("volumes", {})

    def is_available(self) -> bool:
        """Check if Docker is available."""
        import subprocess

        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=5,
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
        """Execute a command in a Docker container."""
        import subprocess

        start_time = time.time()

        cmd_args = [command] + (args or [])
        full_cmd = " ".join(cmd_args)

        docker_cmd = ["docker", "run", "--rm"]

        if self._container_name:
            docker_cmd.extend(["--name", self._container_name])

        for host_path, container_path in self._volumes.items():
            docker_cmd.extend(["-v", f"{host_path}:{container_path}"])

        if cwd:
            docker_cmd.extend(["-w", cwd])

        if self._network:
            docker_cmd.extend(["--network", self._network])

        docker_cmd.append(self._image)
        docker_cmd.append("sh", "-c", full_cmd)

        logger.debug(f"Executing in Docker: {' '.join(docker_cmd)}")

        try:
            proc = subprocess.run(
                docker_cmd,
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
                error="Docker not found. Is Docker installed?",
                exit_code=-1,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Docker execution failed: {e}")
            return ExecutionResult(
                success=False,
                error=str(e),
                exit_code=-1,
                duration_ms=duration_ms,
            )

    def list_containers(self) -> list[dict[str, str]]:
        """List running Docker containers."""
        import json
        import subprocess

        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{json .}}"],
                capture_output=True,
                text=True,
            )

            containers = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    containers.append(json.loads(line))

            return containers

        except Exception as e:
            logger.error(f"Failed to list containers: {e}")
            return []

    def pull_image(self) -> bool:
        """Pull the Docker image."""
        import subprocess

        try:
            subprocess.run(
                ["docker", "pull", self._image],
                check=True,
            )
            return True
        except subprocess.SubprocessError as e:
            logger.error(f"Failed to pull image: {e}")
            return False
