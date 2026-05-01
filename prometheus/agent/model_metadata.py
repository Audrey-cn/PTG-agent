"""Model metadata and context utilities for Prometheus."""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Known context limits for common models
MODEL_CONTEXT_LIMITS = {
    "gpt-4": 8192,
    "gpt-4-32k": 32768,
    "gpt-4-turbo": 128000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-3.5-turbo": 16385,
    "claude-3-opus": 200000,
    "claude-3-sonnet": 200000,
    "claude-3.5-sonnet": 200000,
    "claude-3.5-haiku": 200000,
    "claude-2.1": 200000,
    "claude-2": 100000,
    "gemini-1.5-pro": 1000000,
    "gemini-1.5-flash": 1000000,
    "gemini-2.0-flash": 1000000,
    "gemini-pro": 30720,
    "claude-3-haiku": 200000,
    "o1-preview": 128000,
    "o1-mini": 128000,
}

# Local inference servers
LOCAL_ENDPOINTS = [
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
]


def is_local_endpoint(base_url: str) -> bool:
    """Check if the base URL is a local inference endpoint."""
    if not base_url:
        return False
    return any(endpoint in base_url.lower() for endpoint in LOCAL_ENDPOINTS)


def estimate_tokens_rough(text: str) -> int:
    """Rough token estimation (≈4 chars per token for English)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def estimate_messages_tokens_rough(messages: list[dict[str, Any]]) -> int:
    """Estimate total tokens in a messages list."""
    total = 0
    for msg in messages:
        if isinstance(msg, dict):
            content = msg.get("content", "")
            if isinstance(content, str):
                total += estimate_tokens_rough(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        text = part.get("text", "")
                        total += estimate_tokens_rough(text)
    return total


def estimate_request_tokens_rough(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> int:
    """Estimate tokens for a complete request."""
    tokens = estimate_messages_tokens_rough(messages)

    if tools:
        for tool in tools:
            if isinstance(tool, dict):
                name = tool.get("name", "")
                desc = tool.get("description", "")
                params = tool.get("parameters", {})
                tokens += estimate_tokens_rough(name)
                tokens += estimate_tokens_rough(desc)
                if isinstance(params, dict):
                    import json

                    tokens += estimate_tokens_rough(json.dumps(params))

    return tokens


def get_model_context_limit(model: str) -> int:
    """Get the context limit for a model."""
    model_lower = model.lower()

    for known_model, limit in MODEL_CONTEXT_LIMITS.items():
        if known_model in model_lower:
            return limit

    return 128000


def parse_context_limit_from_error(error_message: str) -> int | None:
    """Parse context limit from an error message.

    Args:
        error_message: The error message string

    Returns:
        The parsed context limit, or None if not found
    """
    error_lower = error_message.lower()

    patterns = [
        r"context length exceeds (\d+)",
        r"maximum context.*?(\d+)",
        r"context window.*?(\d+)",
        r"exceeds the limit of (\d+)",
        r"token limit.*?(\d+)",
        r"(\d+) tokens?",
        r"max_model_len.*?(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, error_lower)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                continue

    return None


def parse_available_output_tokens_from_error(error_message: str) -> int | None:
    """Parse available output tokens from an error message."""
    error_lower = error_message.lower()

    patterns = [
        r"maximum output.*?(\d+)",
        r"available output.*?(\d+)",
        r"output tokens.*?(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, error_lower)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                continue

    return None


def save_context_length(context_length: int, model: str, storage_path: str | None = None) -> None:
    """Save context length for a model to disk."""
    try:
        import json
        from pathlib import Path

        if storage_path is None:
            storage_path = Path.home() / ".prometheus" / "model_context_lengths.json"

        storage = Path(storage_path)
        storage.parent.mkdir(parents=True, exist_ok=True)

        data = {}
        if storage.exists():
            with open(storage) as f:
                data = json.load(f)

        data[model] = context_length

        with open(storage, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save context length: {e}")


def get_saved_context_length(model: str, storage_path: str | None = None) -> int | None:
    """Get saved context length for a model."""
    try:
        import json
        from pathlib import Path

        if storage_path is None:
            storage_path = Path.home() / ".prometheus" / "model_context_lengths.json"

        storage = Path(storage_path)
        if not storage.exists():
            return None

        with open(storage) as f:
            data = json.load(f)

        return data.get(model)
    except Exception:
        return None


async def query_ollama_num_ctx(base_url: str) -> int | None:
    """Query Ollama server for its num_ctx value."""
    try:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base_url}/api/tags") as response:
                if response.status == 200:
                    data = await response.json()
                    if "models" in data and len(data["models"]) > 0:
                        model_name = data["models"][0].get("name", "")
                        return get_model_context_limit(model_name)
    except Exception as e:
        logger.debug(f"Failed to query Ollama num_ctx: {e}")

    return None


class ModelMetadata:
    """Model metadata container."""

    def __init__(
        self,
        model: str,
        context_limit: int = 128000,
        max_output_tokens: int = 4096,
        supports_tools: bool = True,
        supports_vision: bool = False,
        supports_streaming: bool = True,
        is_local: bool = False,
    ):
        self.model = model
        self.context_limit = context_limit
        self.max_output_tokens = max_output_tokens
        self.supports_tools = supports_tools
        self.supports_vision = supports_vision
        self.supports_streaming = supports_streaming
        self.is_local = is_local

    def __repr__(self) -> str:
        return (
            f"ModelMetadata(model={self.model}, context_limit={self.context_limit}, "
            f"max_output={self.max_output_tokens}, tools={self.supports_tools})"
        )


async def fetch_model_metadata(
    model: str,
    base_url: str | None = None,
    api_key: str | None = None,
) -> ModelMetadata:
    """Fetch metadata for a model.

    Args:
        model: Model name
        base_url: Optional base URL for inference server
        api_key: Optional API key

    Returns:
        ModelMetadata instance
    """
    context_limit = get_model_context_limit(model)
    is_local = is_local_endpoint(base_url or "")

    if is_local and base_url and "ollama" in base_url.lower():
        ollama_ctx = await query_ollama_num_ctx(base_url)
        if ollama_ctx:
            context_limit = ollama_ctx

    supports_tools = not is_local
    supports_vision = any(x in model.lower() for x in ["vision", "4o", "claude-3"])

    return ModelMetadata(
        model=model,
        context_limit=context_limit,
        max_output_tokens=4096,
        supports_tools=supports_tools,
        supports_vision=supports_vision,
        is_local=is_local,
    )


def get_next_probe_tier(current_tier: int) -> int:
    """Get the next probe tier for model selection.

    Higher tiers probe more models before settling.
    """
    return min(current_tier + 1, 3)


class TokenCounter:
    """Simple token counter for estimation."""

    def __init__(self, model: str = "gpt-4"):
        self.model = model
        self._encoding = None

    def count(self, text: str) -> int:
        """Count tokens in text."""
        return estimate_tokens_rough(text)

    def count_messages(self, messages: list[dict[str, Any]]) -> int:
        """Count tokens in messages."""
        return estimate_messages_tokens_rough(messages)

    def count_request(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> int:
        """Count tokens for a complete request."""
        return estimate_request_tokens_rough(messages, tools)
