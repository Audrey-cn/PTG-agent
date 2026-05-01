"""OpenAI Chat Completions transport."""

from typing import Any

from prometheus.agent.transports.base import (
    NormalizedResponse,
    ProviderTransport,
    ToolCall,
    Usage,
)


class ChatCompletionsTransport(ProviderTransport):
    """Transport for api_mode='chat_completions'."""

    @property
    def api_mode(self) -> str:
        return "chat_completions"

    def convert_messages(self, messages: list[dict[str, Any]], **kwargs) -> list[dict[str, Any]]:
        """Messages are already in OpenAI format."""
        return messages

    def convert_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Tools are already in OpenAI format."""
        return tools

    def build_kwargs(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **params,
    ) -> dict[str, Any]:
        """Build chat.completions.create() kwargs."""
        kwargs = {
            "model": model,
            "messages": messages,
        }

        if tools:
            kwargs["tools"] = tools

        timeout = params.get("timeout")
        if timeout is not None:
            kwargs["timeout"] = timeout

        temperature = params.get("temperature")
        if temperature is not None:
            kwargs["temperature"] = temperature

        max_tokens = params.get("max_tokens")
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        return kwargs

    def normalize_response(self, response: Any, **kwargs) -> NormalizedResponse:
        """Normalize OpenAI ChatCompletion to NormalizedResponse."""
        choice = response.get("choices", [{}])[0]
        msg = choice.get("message", {})

        tool_calls = None
        raw_tc = msg.get("tool_calls")
        if raw_tc:
            tool_calls = []
            for tc in raw_tc:
                func = tc.get("function", {})
                tool_calls.append(
                    ToolCall(
                        id=tc.get("id", ""),
                        name=func.get("name", ""),
                        arguments=func.get("arguments", ""),
                    )
                )

        usage = None
        raw_usage = response.get("usage")
        if raw_usage:
            usage = Usage(
                prompt_tokens=raw_usage.get("prompt_tokens", 0),
                completion_tokens=raw_usage.get("completion_tokens", 0),
                total_tokens=raw_usage.get("total_tokens", 0),
            )

        return NormalizedResponse(
            content=msg.get("content"),
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason", "stop"),
            reasoning=msg.get("reasoning"),
            usage=usage,
            provider_data={},
        )

    def validate_response(self, response: Any) -> bool:
        """Check that response has valid choices."""
        if response is None:
            return False
        return response.get("choices")

    def extract_cache_stats(self, response: Any) -> dict[str, int] | None:
        """Extract cache stats from response."""
        usage = response.get("usage", {})
        details = usage.get("prompt_tokens_details", {})
        if details:
            cached = details.get("cached_tokens", 0)
            written = details.get("cache_write_tokens", 0)
            if cached or written:
                return {"cached_tokens": cached, "creation_tokens": written}
        return None


from prometheus.agent.transports import register_transport

register_transport("chat_completions", ChatCompletionsTransport)
