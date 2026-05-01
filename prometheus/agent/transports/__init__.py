"""Prometheus Agent Transports."""

from prometheus.agent.transports.types import NormalizedResponse, ProviderTransport, ToolCall, Usage

_TRANSPORTS = {}


def register_transport(api_mode: str, transport_cls):
    """Register a transport class for an api_mode."""
    _TRANSPORTS[api_mode] = transport_cls


def get_transport(api_mode: str) -> ProviderTransport:
    """Get a transport instance for an api_mode."""
    if api_mode in _TRANSPORTS:
        return _TRANSPORTS[api_mode]()
    return _TRANSPORTS.get("chat_completions", ChatCompletionsTransport)()


def list_transports():
    """List all registered transports."""
    return list(_TRANSPORTS.keys())


class ChatCompletionsTransportPlaceholder(ProviderTransport):
    """Placeholder for ChatCompletionsTransport until full implementation."""

    @property
    def api_mode(self) -> str:
        return "chat_completions"

    def convert_messages(self, messages, **kwargs):
        return messages

    def convert_tools(self, tools):
        return tools

    def build_kwargs(self, model, messages, tools=None, **params):
        return {"model": model, "messages": messages, "tools": tools or []}

    def normalize_response(self, response, **kwargs):
        return NormalizedResponse(
            content=response.get("content"),
            tool_calls=None,
            finish_reason=response.get("finish_reason", "stop"),
            reasoning=None,
            usage=None,
            provider_data=None,
        )


_TRANSPORTS["chat_completions"] = ChatCompletionsTransportPlaceholder

__all__ = [
    "ProviderTransport",
    "NormalizedResponse",
    "ToolCall",
    "Usage",
    "register_transport",
    "get_transport",
    "list_transports",
]
