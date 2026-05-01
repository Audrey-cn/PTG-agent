"""Honcho memory integration for Prometheus."""

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("prometheus.honcho")

HONCHO_CONFIG_FILE = Path.home() / ".prometheus" / "honcho_config.json"


class HonchoMemoryMode:
    """Memory mode types."""

    NATIVE = "native"
    HONCHO = "honcho"
    HYBRID = "hybrid"


class HonchoConfig:
    """Honcho configuration."""

    def __init__(
        self,
        enabled: bool = False,
        mode: str = HonchoMemoryMode.NATIVE,
        session_context_tokens: int = 10000,
        dialectic_tokens: int = 2000,
        user_peer_name: str = "User",
        ai_peer_name: str = "Prometheus",
        dialectic_level: str = "standard",
    ):
        self.enabled = enabled
        self.mode = mode
        self.session_context_tokens = session_context_tokens
        self.dialectic_tokens = dialectic_tokens
        self.user_peer_name = user_peer_name
        self.ai_peer_name = ai_peer_name
        self.dialectic_level = dialectic_level

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "session_context_tokens": self.session_context_tokens,
            "dialectic_tokens": self.dialectic_tokens,
            "user_peer_name": self.user_peer_name,
            "ai_peer_name": self.ai_peer_name,
            "dialectic_level": self.dialectic_level,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HonchoConfig":
        return cls(
            enabled=data.get("enabled", False),
            mode=data.get("mode", HonchoMemoryMode.NATIVE),
            session_context_tokens=data.get("session_context_tokens", 10000),
            dialectic_tokens=data.get("dialectic_tokens", 2000),
            user_peer_name=data.get("user_peer_name", "User"),
            ai_peer_name=data.get("ai_peer_name", "Prometheus"),
            dialectic_level=data.get("dialectic_level", "standard"),
        )


class HonchoClient:
    """Client for Honcho AI memory service."""

    def __init__(self, config: HonchoConfig | None = None):
        self._config = config or HonchoConfig()
        self._session_mappings: dict[str, str] = {}

    def configure(self, **kwargs):
        """Update configuration."""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)

    def setup(self) -> bool:
        """Set up Honcho integration.

        Returns:
            True if setup was successful
        """
        if not self._config.enabled:
            logger.info("Honcho integration is disabled")
            return False

        try:
            self._save_config()
            logger.info("Honcho integration setup complete")
            return True
        except Exception as e:
            logger.error(f"Honcho setup failed: {e}")
            return False

    def get_status(self) -> dict[str, Any]:
        """Get Honcho integration status."""
        return {
            "enabled": self._config.enabled,
            "mode": self._config.mode,
            "session_mappings": len(self._session_mappings),
        }

    def map_directory(self, directory: str, session_name: str):
        """Map a directory to a session name."""
        self._session_mappings[os.path.abspath(directory)] = session_name
        self._save_config()

    def get_session_for_directory(self, directory: str) -> str | None:
        """Get the session name for a directory."""
        abs_dir = os.path.abspath(directory)
        return self._session_mappings.get(abs_dir)

    def list_sessions(self) -> list[dict[str, str]]:
        """List directory to session mappings."""
        return [{"directory": d, "session": s} for d, s in self._session_mappings.items()]

    def get_peer_names(self) -> tuple:
        """Get (user_peer_name, ai_peer_name)."""
        return (self._config.user_peer_name, self._config.ai_peer_name)

    def set_peer_names(self, user_name: str, ai_name: str):
        """Set peer names."""
        self._config.user_peer_name = user_name
        self._config.ai_peer_name = ai_name
        self._save_config()

    def get_dialectic_level(self) -> str:
        """Get dialectic reasoning level."""
        return self._config.dialectic_level

    def set_dialectic_level(self, level: str):
        """Set dialectic reasoning level (basic, standard, advanced)."""
        self._config.dialectic_level = level
        self._save_config()

    def get_token_settings(self) -> dict[str, int]:
        """Get token budget settings."""
        return {
            "session_context": self._config.session_context_tokens,
            "dialectic": self._config.dialectic_tokens,
        }

    def set_token_settings(self, session_context: int = None, dialectic: int = None):
        """Set token budget settings."""
        if session_context is not None:
            self._config.session_context_tokens = session_context
        if dialectic is not None:
            self._config.dialectic_tokens = dialectic
        self._save_config()

    def _save_config(self):
        """Save configuration to disk."""
        HONCHO_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(HONCHO_CONFIG_FILE, "w") as f:
            json.dump(self._config.to_dict(), f, indent=2)

    @classmethod
    def load(cls) -> Optional["HonchoClient"]:
        """Load Honcho configuration from disk."""
        if not HONCHO_CONFIG_FILE.exists():
            return None

        try:
            with open(HONCHO_CONFIG_FILE) as f:
                data = json.load(f)
            config = HonchoConfig.from_dict(data)
            return cls(config)
        except Exception as e:
            logger.error(f"Failed to load Honcho config: {e}")
            return None


class HonchoMemoryIntegration:
    """Integration layer for Honcho memory capabilities."""

    def __init__(self, client: HonchoClient | None = None):
        self._client = client

    def get_context_for_session(
        self,
        session_name: str,
        max_tokens: int = 10000,
    ) -> list[dict[str, Any]]:
        """Get memory context for a session.

        Args:
            session_name: Name of the session
            max_tokens: Maximum tokens to retrieve

        Returns:
            List of memory messages
        """
        if not self._client or not self._client._config.enabled:
            return []

        try:
            return self._fetch_honcho_context(session_name, max_tokens)
        except Exception as e:
            logger.error(f"Failed to get Honcho context: {e}")
            return []

    def _fetch_honcho_context(
        self,
        session_name: str,
        max_tokens: int,
    ) -> list[dict[str, Any]]:
        """Fetch context from Honcho service.

        Tries to import the Honcho SDK and fetch context. If SDK is not
        available or not configured, falls back to empty context.
        """
        try:
            from honcho import Honcho

            client = Honcho()
            response = client.context(
                session=session_name,
                max_tokens=max_tokens,
            )
            if response and hasattr(response, "messages"):
                return response.messages
            return []
        except ImportError:
            logger.debug("Honcho SDK not installed, skipping context fetch")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch Honcho context: {e}")
            return []

    def get_honcho_sessions(self) -> list[dict[str, str]]:
        """List available Honcho sessions.

        Returns:
            List of session dicts with 'name' and 'id' keys
        """
        try:
            from honcho import Honcho

            client = Honcho()
            sessions = client.sessions.list()
            return [{"id": s.get("id", ""), "name": s.get("name", "")} for s in sessions]
        except Exception as e:
            logger.warning(f"Failed to list Honcho sessions: {e}")
            return []

    def create_honcho_session(self, name: str, description: str = "") -> str | None:
        """Create a new Honcho session.

        Args:
            name: Session name
            description: Optional session description

        Returns:
            Session ID if successful
        """
        try:
            from honcho import Honcho

            client = Honcho()
            session = client.sessions.create(name=name, description=description)
            return session.get("id")
        except Exception as e:
            logger.warning(f"Failed to create Honcho session: {e}")
            return None

    def add_honcho_message(
        self,
        session_name: str,
        role: str,
        content: str,
    ) -> bool:
        """Add a message to a Honcho session.

        Args:
            session_name: Session name
            role: Message role (user, assistant)
            content: Message content

        Returns:
            True if successful
        """
        try:
            from honcho import Honcho

            client = Honcho()
            client.messages.add(
                session=session_name,
                role=role,
                content=content,
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to add Honcho message: {e}")
            return False

    def store_memory(
        self,
        session_name: str,
        content: str,
        memory_type: str = "fact",
    ) -> bool:
        """Store a memory in Honcho.

        Args:
            session_name: Name of the session
            content: Content to store
            memory_type: Type of memory (fact, preference, context)

        Returns:
            True if storage was successful
        """
        if not self._client or not self._client._config.enabled:
            return False

        try:
            logger.info(f"Storing {memory_type} in Honcho for session {session_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
            return False

    def get_memory_identity(self) -> str:
        """Get the AI peer identity representation."""
        if not self._client:
            return "Prometheus"

        return self._client._config.ai_peer_name

    def set_memory_identity(self, identity_file: str) -> bool:
        """Seed AI peer identity from a file.

        Args:
            identity_file: Path to identity file (e.g., SOUL.md)

        Returns:
            True if successful
        """
        try:
            identity_path = Path(identity_file)
            if not identity_path.exists():
                return False

            identity_path.read_text(encoding="utf-8")
            logger.info(f"Loaded memory identity from {identity_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to set memory identity: {e}")
            return False


_honcho_client: HonchoClient | None = None
_honcho_integration: HonchoMemoryIntegration | None = None


def get_honcho_client() -> HonchoClient:
    """Get the global Honcho client instance."""
    global _honcho_client
    if _honcho_client is None:
        _honcho_client = HonchoClient.load() or HonchoClient()
    return _honcho_client


def get_honcho_integration() -> HonchoMemoryIntegration:
    """Get the global Honcho integration instance."""
    global _honcho_integration
    if _honcho_integration is None:
        _honcho_integration = HonchoMemoryIntegration(get_honcho_client())
    return _honcho_integration


def setup_honcho(
    mode: str = HonchoMemoryMode.NATIVE,
    session_context_tokens: int = 10000,
    dialectic_tokens: int = 2000,
) -> bool:
    """Set up Honcho integration.

    Args:
        mode: Memory mode (native, honcho, hybrid)
        session_context_tokens: Token budget for session context
        dialectic_tokens: Token budget for dialectic reasoning

    Returns:
        True if setup was successful
    """
    client = get_honcho_client()
    client.configure(
        enabled=True,
        mode=mode,
        session_context_tokens=session_context_tokens,
        dialectic_tokens=dialectic_tokens,
    )
    return client.setup()


def honcho_status() -> dict[str, Any]:
    """Get Honcho integration status."""
    client = get_honcho_client()
    return client.get_status()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Prometheus Honcho Integration")
    subparsers = parser.add_subparsers(dest="command", help="Command")

    setup_parser = subparsers.add_parser("setup", help="Configure Honcho integration")
    setup_parser.add_argument("--mode", choices=["native", "honcho", "hybrid"], default="hybrid")
    setup_parser.add_argument("--context-tokens", type=int, default=10000)
    setup_parser.add_argument("--dialectic-tokens", type=int, default=2000)

    status_parser = subparsers.add_parser("status", help="Show Honcho status")
    sessions_parser = subparsers.add_parser("sessions", help="List session mappings")

    peer_parser = subparsers.add_parser("peer", help="Manage peer names")
    peer_parser.add_argument("--user", help="Set user peer name")
    peer_parser.add_argument("--ai", help="Set AI peer name")

    args = parser.parse_args()

    if args.command == "setup":
        success = setup_honcho(
            mode=args.mode,
            session_context_tokens=args.context_tokens,
            dialectic_tokens=args.dialectic_tokens,
        )
        print(f"Honcho setup {'successful' if success else 'failed'}")

    elif args.command == "status":
        import json

        print(json.dumps(honcho_status(), indent=2))

    elif args.command == "sessions":
        client = get_honcho_client()
        sessions = client.list_sessions()
        for s in sessions:
            print(f"{s['directory']} -> {s['session']}")

    elif args.command == "peer":
        client = get_honcho_client()
        if args.user:
            client.set_peer_names(args.user, client._config.ai_peer_name)
        if args.ai:
            client.set_peer_names(client._config.user_peer_name, args.ai)
        print(f"Peer names: {client.get_peer_names()}")

    else:
        parser.print_help()
