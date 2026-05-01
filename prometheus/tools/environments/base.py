"""Base class for execution environments."""

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of a code execution."""

    success: bool
    output: str = ""
    error: str = ""
    exit_code: int = 0
    duration_ms: float = 0.0
    session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ExecutionEnvironment(ABC):
    """Abstract base class for execution environments.

    Subclass this to implement support for different execution backends
    (Docker, SSH, Modal, Vercel, etc.).
    """

    name: str = "base"
    supports_streaming: bool = False
    supports_cancel: bool = False

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        self._sessions: dict[str, Any] = {}

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this environment is available/configured."""

    @abstractmethod
    def execute(
        self,
        command: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> ExecutionResult:
        """Execute a command and return the result."""

    def execute_interactive(
        self,
        command: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> ExecutionResult:
        """Execute a command interactively (for REPL-style use)."""
        raise NotImplementedError(f"{self.name} does not support interactive execution")

    def create_session(self, name: str | None = None) -> str:
        """Create a persistent execution session."""
        session_id = name or f"session-{uuid.uuid4().hex[:8]}"
        self._sessions[session_id] = {}
        return session_id

    def close_session(self, session_id: str) -> bool:
        """Close a persistent execution session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def get_session_info(self, session_id: str) -> dict[str, Any] | None:
        """Get information about a session."""
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[str]:
        """List all active sessions."""
        return list(self._sessions.keys())


def get_environment(
    name: str,
    config: dict[str, Any] | None = None,
) -> ExecutionEnvironment:
    """Get an execution environment by name.

    Args:
        name: Environment name (local, docker, ssh, modal, etc.)
        config: Optional configuration dict

    Returns:
        ExecutionEnvironment instance

    Raises:
        ValueError: If environment name is unknown
    """
    env_map = {
        "local": "prometheus.tools.environments.local",
        "docker": "prometheus.tools.environments.docker",
        "ssh": "prometheus.tools.environments.ssh",
        "modal": "prometheus.tools.environments.modal",
    }

    if name == "auto":
        name = _detect_best_environment()

    if name not in env_map:
        raise ValueError(f"Unknown environment: {name}. Available: {list(env_map.keys())}")

    import importlib

    module_path = env_map[name]
    try:
        module = importlib.import_module(module_path)
        env_class = getattr(module, f"{name.title()}Environment")
        return env_class(config=config)
    except ImportError:
        logger.warning(f"Failed to import {module_path}, falling back to local")
        return LocalEnvironment(config=config)


def _detect_best_environment() -> str:
    """Detect the best available environment for this system."""
    if DockerEnvironment(config={}).is_available():
        return "docker"
    return "local"


from .docker import DockerEnvironment
from .local import LocalEnvironment
