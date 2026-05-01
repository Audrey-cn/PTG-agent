"""Anthropic Messages API transport."""

from typing import Any

from prometheus.agent.transports.base import (
    NormalizedResponse,
    ProviderTransport,
    ToolCall,
)


class AnthropicTransport(ProviderTransport):
    """Transport for api_mode='anthropic_messages'."""

    @property
    def api_mode(self) -> str:
        return "anthropic_messages"

    def convert_messages(self, messages: list[dict[str, Any]], **kwargs) -> Any:
        """Convert OpenAI messages to Anthropic (system, messages) tuple."""
        system = None
        converted_messages = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            if role == "system":
                system = content
            elif role == "user":
                converted_messages.append({"role": "user", "content": content})
            elif role == "assistant":
                tc = msg.get("tool_calls")
                if tc:
                    tool_results = []
                    for call in tc:
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": call.get("id"),
                                "content": call.get("result", ""),
                            }
                        )
                    converted_messages.append(
                        {
                            "role": "user",
                            "content": tool_results,
                        }
                    )
                else:
                    converted_messages.append({"role": "assistant", "content": content})

        return system, converted_messages

    def convert_tools(self, tools: list[dict[str, Any]]) -> Any:
        """Convert OpenAI tool schemas to Anthropic input_schema format."""
        anthropic_tools = []
        for tool in tools:
            func = tool.get("function", {})
            anthropic_tools.append(
                {
                    "name": func.get("name"),
                    "description": func.get("description"),
                    "input_schema": func.get("parameters", {}),
                }
            )
        return anthropic_tools

    def build_kwargs(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **params,
    ) -> dict[str, Any]:
        """Build Anthropic messages.create() kwargs."""
        system, converted = self.convert_messages(messages)

        kwargs = {
            "model": model,
            "max_tokens": params.get("max_tokens", 16384),
        }

        if system:
            kwargs["system"] = system

        kwargs["messages"] = converted

        if tools:
            kwargs["tools"] = self.convert_tools(tools)

        return kwargs

    def normalize_response(self, response: Any, **kwargs) -> NormalizedResponse:
        """Normalize Anthropic response to NormalizedResponse."""
        text_parts = []
        tool_calls = []

        for block in response.get("content", []):
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.get("id"),
                        name=block.get("name"),
                        arguments=str(block.get("input", {})),
                    )
                )

        return NormalizedResponse(
            content="\n".join(text_parts) if text_parts else None,
            tool_calls=tool_calls or None,
            finish_reason=response.get("stop_reason", "stop"),
            reasoning=response.get("thinking", None),
            usage=None,
            provider_data={},
        )

    def extract_cache_stats(self, response: Any) -> dict[str, int] | None:
        """Extract Anthropic cache stats."""
        usage = response.get("usage", {})
        if usage:
            cached = usage.get("cache_read_input_tokens", 0)
            written = usage.get("cache_creation_input_tokens", 0)
            if cached or written:
                return {"cached_tokens": cached, "creation_tokens": written}
        return None


from prometheus.agent.transports import register_transport

register_transport("anthropic_messages", AnthropicTransport)
