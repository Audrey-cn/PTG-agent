"""Abstract base class for pluggable memory providers."""

import contextlib
from abc import ABC, abstractmethod
from typing import Any


class MemoryProvider(ABC):
    """Abstract base class for memory providers.

    One external provider is active at a time alongside the built-in memory
    (USER.md / MEMORY.md / SOUL.md). The MemoryManager enforces this limit.

    Built-in memory is always active as the first provider and cannot be removed.
    External providers (Honcho, Hindsight, Mem0, etc.) are additive — they never
    disable the built-in store. Only one external provider runs at a time to
    prevent tool schema bloat and conflicting memory backends.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier for this provider (e.g. 'builtin', 'honcho')."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this provider is configured and ready.

        Should not make network calls — just check config and installed deps.
        """

    @abstractmethod
    def initialize(self, session_id: str, **kwargs) -> None:
        """Initialize for a session.

        May create resources, establish connections, start background threads.

        kwargs always include:
          - hermes_home (str): The active PROMETHEUS_HOME directory path.
          - platform (str): "cli", "telegram", "discord", "cron", etc.

        kwargs may also include:
          - agent_context (str): "primary", "subagent", "cron", or "flush".
          - agent_identity (str): Profile name.
          - agent_workspace (str): Shared workspace name.
          - parent_session_id (str): For subagents.
          - user_id (str): Platform user identifier.
        """

    def system_prompt_block(self) -> str:
        """Return text to include in the system prompt.

        Return empty string to skip.
        This is for STATIC provider info (instructions, status).
        """
        return ""

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """Recall relevant context for the upcoming turn.

        Called before each API call. Return formatted text to inject.
        Implementations should be fast — use background threads for recall.
        """
        return ""

    def sync_turn(self, user: str, assistant: str) -> None:
        """Async write after each turn.

        Called after each agent turn to store the exchange.
        """
        pass

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """Return tool schemas to expose to the model.

        Return empty list to skip.
        Tools are only exposed for the active external provider.
        """
        return []

    def handle_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Dispatch a tool call from the model.

        Return the result as a string.
        Raise ValueError for unknown tools.
        """
        raise ValueError(f"Unknown tool: {tool_name}")

    def shutdown(self) -> None:
        """Clean exit."""
        pass

    def on_turn_start(self, turn: int, message: str, **kwargs) -> None:
        """Per-turn tick with runtime context (optional hook)."""
        pass

    def on_session_end(self, messages: list[dict[str, Any]], **kwargs) -> None:
        """End-of-session extraction (optional hook)."""
        pass

    def on_session_switch(self, new_session_id: str, **kwargs) -> None:
        """Mid-process session_id rotation (optional hook)."""
        pass

    def on_pre_compress(self, messages: list[dict[str, Any]]) -> str:
        """Extract before context compression (optional hook).

        Return a string to inject into the compression summary.
        """
        return ""

    def on_memory_write(
        self,
        action: str,
        target: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Mirror built-in memory writes (optional hook).

        Args:
            action: "create" or "update"
            target: "USER.md" or "MEMORY.md"
            content: Content that was written
            metadata: Optional metadata
        """
        pass

    def on_delegation(
        self,
        task: str,
        result: str,
        **kwargs,
    ) -> None:
        """Parent-side observation of subagent work (optional hook).

        Args:
            task: Task description
            result: Task result summary
        """
        pass


class MemoryProviderRegistry:
    """Registry for memory providers."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._providers: dict[str, type] = {}
            cls._instance._active_provider: MemoryProvider | None = None
        return cls._instance

    def register(self, name: str, provider_class: type) -> None:
        """Register a memory provider class.

        Args:
            name: Provider name
            provider_class: Class implementing MemoryProvider
        """
        if not issubclass(provider_class, MemoryProvider):
            raise TypeError(f"{provider_class} must inherit from MemoryProvider")
        self._providers[name] = provider_class

    def create_provider(self, name: str) -> MemoryProvider | None:
        """Create a provider instance by name.

        Args:
            name: Provider name

        Returns:
            Provider instance or None
        """
        provider_class = self._providers.get(name)
        if provider_class:
            return provider_class()
        return None

    def get_provider_class(self, name: str) -> type | None:
        """Get a provider class by name."""
        return self._providers.get(name)

    def list_providers(self) -> list[str]:
        """List all registered provider names."""
        return list(self._providers.keys())

    def set_active(self, provider: MemoryProvider | None) -> None:
        """Set the active external memory provider."""
        self._active_provider = provider

    def get_active(self) -> MemoryProvider | None:
        """Get the active external memory provider."""
        return self._active_provider


_global_registry: MemoryProviderRegistry | None = None


def get_memory_provider_registry() -> MemoryProviderRegistry:
    """Get the global memory provider registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = MemoryProviderRegistry()
    return _global_registry


def register_memory_provider(name: str, provider_class: type) -> None:
    """Register a memory provider.

    Args:
        name: Provider name
        provider_class: Class implementing MemoryProvider
    """
    get_memory_provider_registry().register(name, provider_class)


class BuiltinMemoryProvider(MemoryProvider):
    """Built-in memory provider using USER.md and MEMORY.md files.

    Always present and cannot be removed.
    """

    @property
    def name(self) -> str:
        return "builtin"

    def is_available(self) -> bool:
        return True

    def initialize(self, session_id: str, **kwargs) -> None:
        pass

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        return []

    def handle_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> str:
        raise ValueError("Builtin provider handles no tools")


class HonchoMemoryProvider(MemoryProvider):
    """Honcho AI memory integration.

    Provides cross-session memory with Honcho backend.
    """

    def __init__(self):
        self._client = None
        self._initialized = False

    @property
    def name(self) -> str:
        return "honcho"

    def is_available(self) -> bool:
        try:
            from prometheus.honcho_integration import get_honcho_client

            client = get_honcho_client()
            return client._config.enabled
        except Exception:
            return False

    def initialize(self, session_id: str, **kwargs) -> None:
        from prometheus.honcho_integration import get_honcho_client

        self._client = get_honcho_client()
        self._initialized = True

    def system_prompt_block(self) -> str:
        return ""

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if not self._client:
            return ""

        try:
            integration = self._client.get_integration()
            context = integration.get_context_for_session(
                session_name=session_id,
                max_tokens=self._client._config.session_context_tokens,
            )
            return context
        except Exception:
            return ""

    def sync_turn(self, user: str, assistant: str) -> None:
        if not self._client:
            return

        with contextlib.suppress(Exception):
            self._client.store_memory(
                session_name=self._client._session_id,
                content=f"User: {user}\nAssistant: {assistant}",
                memory_type="conversation",
            )

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        return []

    def shutdown(self) -> None:
        self._initialized = False


register_memory_provider("builtin", BuiltinMemoryProvider)
register_memory_provider("honcho", HonchoMemoryProvider)
