"""Memory context building for Prometheus."""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

REASONING_TAGS = (
    "REASONING_SCRATCHPAD",
    "think",
    "thinking",
    "reasoning",
    "thought",
)


def strip_reasoning_tags(text: str) -> str:
    """Remove reasoning/thinking blocks from text."""
    cleaned = text
    for tag in REASONING_TAGS:
        cleaned = re.sub(
            rf"<{tag}>.*?</{tag}>\s*",
            "",
            cleaned,
            flags=re.DOTALL | re.IGNORECASE,
        )
        cleaned = re.sub(
            rf"<{tag}>.*$",
            "",
            cleaned,
            flags=re.DOTALL | re.IGNORECASE,
        )
        cleaned = re.sub(
            rf"</{tag}>\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
    return cleaned.strip()


class StreamingContextScrubber:
    """Scrub streaming responses in real-time.

    Removes thinking/reasoning blocks from streaming output
    as it arrives, before it gets added to context.
    """

    def __init__(self):
        self._buffer = ""
        self._in_tag = False
        self._current_tag = None
        self._remove_until_close = False

    def process(self, text: str) -> str:
        """Process incoming text and remove reasoning blocks.

        Returns the cleaned text.
        """
        result = []
        i = 0

        while i < len(text):
            if self._remove_until_close:
                tag_end = text.find(">", i)
                if tag_end != -1:
                    self._remove_until_close = False
                    i = tag_end + 1
                    continue
                else:
                    i = len(text)
                    continue

            if self._in_tag:
                if text[i] == ">":
                    self._in_tag = False
                    self._current_tag = None
                i += 1
                continue

            if text[i] == "<":
                for tag in REASONING_TAGS:
                    tag_pattern = f"<{tag}"
                    if text[i:].lower().startswith(tag_pattern.lower()):
                        self._in_tag = True
                        self._current_tag = tag
                        if text[i:].startswith(f"</{tag}"):
                            self._remove_until_close = True
                        break
                else:
                    result.append(text[i])
                i += 1
                continue

            result.append(text[i])
            i += 1

        self._buffer = "".join(result)
        return self._buffer

    def flush(self) -> str:
        """Flush any remaining content."""
        return self._buffer

    def reset(self):
        """Reset the scrubber state."""
        self._buffer = ""
        self._in_tag = False
        self._current_tag = None
        self._remove_until_close = False


def sanitize_context(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sanitize messages by removing reasoning blocks and cleaning content.

    Args:
        messages: List of message dictionaries

    Returns:
        Sanitized messages list
    """
    sanitized = []

    for msg in messages:
        if not isinstance(msg, dict):
            continue

        sanitized_msg = msg.copy()

        content = msg.get("content")
        if isinstance(content, str):
            sanitized_msg["content"] = strip_reasoning_tags(content)
        elif isinstance(content, list):
            new_content = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    new_part = part.copy()
                    if "text" in new_part:
                        new_part["text"] = strip_reasoning_tags(new_part["text"])
                    new_content.append(new_part)
                else:
                    new_content.append(part)
            sanitized_msg["content"] = new_content

        sanitized.append(sanitized_msg)

    return sanitized


def build_memory_context_block(
    memory_messages: list[dict[str, Any]],
    memory_guidance: str = "",
    session_search_guidance: str = "",
    max_memory_tokens: int = 10000,
) -> tuple[list[dict[str, Any]], int]:
    """Build a memory context block from memory messages.

    Args:
        memory_messages: List of memory messages to include
        memory_guidance: Optional guidance for how to use memory
        session_search_guidance: Optional guidance for session search
        max_memory_tokens: Maximum tokens for memory block

    Returns:
        Tuple of (memory_block, estimated_tokens)
    """
    from .model_metadata import estimate_tokens_rough

    memory_block = []

    if memory_guidance:
        memory_block.append(
            {
                "role": "system",
                "content": memory_guidance,
            }
        )

    if session_search_guidance:
        memory_block.append(
            {
                "role": "system",
                "content": session_search_guidance,
            }
        )

    current_tokens = estimate_tokens_rough(str(memory_block))

    for msg in memory_messages:
        msg_tokens = estimate_tokens_rough(str(msg))

        if current_tokens + msg_tokens > max_memory_tokens:
            break

        memory_block.append(msg)
        current_tokens += msg_tokens

    return memory_block, current_tokens


def load_soul_md(soul_path: str | None = None) -> str:
    """Load SOUL.md content.

    Args:
        soul_path: Optional path to SOUL.md

    Returns:
        Content of SOUL.md or empty string
    """
    from pathlib import Path

    if soul_path is None:
        prom_home = Path.home() / ".prometheus"
        soul_path = prom_home / "SOUL.md"

    soul_file = Path(soul_path)
    if not soul_file.exists():
        return ""

    try:
        return soul_file.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to load SOUL.md: {e}")
        return ""


DEFAULT_MEMORY_GUIDANCE = """You have access to memory from previous sessions. Use this information to maintain context and continuity across conversations."""

DEFAULT_SESSION_SEARCH_GUIDANCE = """To find relevant information from previous sessions, use the session_search tool with a query that matches the user's information need."""


class MemoryContextBuilder:
    """Builder for constructing memory context blocks."""

    def __init__(
        self,
        max_memory_tokens: int = 10000,
        memory_guidance: str = DEFAULT_MEMORY_GUIDANCE,
        session_search_guidance: str = DEFAULT_SESSION_SEARCH_GUIDANCE,
    ):
        self.max_memory_tokens = max_memory_tokens
        self.memory_guidance = memory_guidance
        self.session_search_guidance = session_search_guidance

    def build(
        self,
        memory_messages: list[dict[str, Any]],
        prepend_system: bool = True,
    ) -> list[dict[str, Any]]:
        """Build memory context block.

        Args:
            memory_messages: List of memory messages
            prepend_system: Whether to prepend system guidance

        Returns:
            Memory context block
        """
        if not prepend_system:
            return memory_messages[: self._calculate_allowed_count(memory_messages)]

        return build_memory_context_block(
            memory_messages,
            self.memory_guidance,
            self.session_search_guidance,
            self.max_memory_tokens,
        )[0]

    def _calculate_allowed_count(self, messages: list[dict[str, Any]]) -> int:
        """Calculate how many messages fit in the budget."""
        from .model_metadata import estimate_tokens_rough

        allowed = len(messages)
        total_tokens = 0

        for i, msg in enumerate(messages):
            total_tokens += estimate_tokens_rough(str(msg))
            if total_tokens > self.max_memory_tokens:
                allowed = i
                break

        return allowed
