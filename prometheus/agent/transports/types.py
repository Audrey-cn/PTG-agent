"""Abstract base for provider transports."""

from abc import ABC, abstractmethod
from typing import Any


class NormalizedResponse:
    """Normalized response from any provider."""

    def __init__(
        self,
        content: str | None = None,
        tool_calls: list[Any] | None = None,
        finish_reason: str = "stop",
        reasoning: str | None = None,
        usage: Any | None = None,
        provider_data: dict[str, Any] | None = None,
    ):
        self.content = content
        self.tool_calls = tool_calls
        self.finish_reason = finish_reason
        self.reasoning = reasoning
        self.usage = usage
        self.provider_data = provider_data or {}


class ToolCall:
    """Normalized tool call."""

    def __init__(
        self,
        id: str,
        name: str,
        arguments: str,
        provider_data: dict[str, Any] | None = None,
    ):
        self.id = id
        self.name = name
        self.arguments = arguments
        self.provider_data = provider_data or {}


class Usage:
    """Normalized token usage."""

    def __init__(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        cached_tokens: int = 0,
        reasoning_tokens: int = 0,
    ):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
        self.cached_tokens = cached_tokens
        self.reasoning_tokens = reasoning_tokens


class ProviderTransport(ABC):
    """Base class for provider-specific format conversion and normalization."""

    @property
    @abstractmethod
    def api_mode(self) -> str:
        """The api_mode string this transport handles."""
        ...

    @abstractmethod
    def convert_messages(self, messages: list[dict[str, Any]], **kwargs) -> Any:
        """Convert OpenAI-format messages to provider-native format."""
        ...

    @abstractmethod
    def convert_tools(self, tools: list[dict[str, Any]]) -> Any:
        """Convert OpenAI-format tool definitions to provider-native format."""
        ...

    @abstractmethod
    def build_kwargs(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **params,
    ) -> dict[str, Any]:
        """Build the complete API call kwargs dict."""
        ...

    @abstractmethod
    def normalize_response(self, response: Any, **kwargs) -> NormalizedResponse:
        """Normalize a raw provider response to the shared NormalizedResponse type."""
        ...

    def validate_response(self, response: Any) -> bool:
        """Optional: check if the raw response is structurally valid."""
        return True

    def extract_cache_stats(self, response: Any) -> dict[str, int] | None:
        """Optional: extract provider-specific cache hit/creation stats."""
        return None

    def map_finish_reason(self, raw_reason: str) -> str:
        """Optional: map provider-specific stop reason to OpenAI equivalent."""
        return raw_reason
