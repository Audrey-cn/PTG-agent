"""Prompt caching utilities for Anthropic API."""

import logging
from typing import Any

logger = logging.getLogger(__name__)

CACHE_CONTROL_EMOJI = "\ue251"


def apply_anthropic_cache_control(
    messages: list[dict[str, Any]],
    cache_threshold: float = 0.75,
) -> list[dict[str, Any]]:
    """Apply Anthropic cache control to messages.

    Args:
        messages: List of message dictionaries
        cache_threshold: Threshold (0-1) for caching older messages

    Returns:
        Messages with cache control applied
    """
    if not messages:
        return messages

    protected_roles = {"system"}
    cacheable_roles = {"user", "assistant"}

    result = []
    cache_candidates = []

    for msg in messages:
        role = msg.get("role", "")

        if role in protected_roles:
            result.append(msg.copy())
            continue

        if role in cacheable_roles:
            cache_candidates.append(msg)
            continue

        result.append(msg.copy())

    if not cache_candidates:
        return result

    cutoff_index = int(len(cache_candidates) * cache_threshold)
    cutoff_index = max(1, cutoff_index)

    for i, msg in enumerate(cache_candidates):
        if i < cutoff_index:
            msg_with_cache = msg.copy()
            content = msg_with_cache.get("content")

            if isinstance(content, str):
                msg_with_cache["content"] = [
                    {"type": "text", "text": content, "cache_control": {"type": "ephemeral"}},
                ]
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        part["cache_control"] = {"type": "ephemeral"}
                        break
                else:
                    content.append(
                        {"type": "text", "text": "", "cache_control": {"type": "ephemeral"}}
                    )

            result.append(msg_with_cache)
        else:
            result.append(msg)

    return result


def remove_anthropic_cache_control(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Remove Anthropic cache control from messages.

    Args:
        messages: List of message dictionaries with cache control

    Returns:
        Messages with cache control removed
    """
    result = []

    for msg in messages:
        cleaned_msg = msg.copy()
        content = msg.get("content")

        if isinstance(content, list):
            new_content = []
            for part in content:
                if isinstance(part, dict):
                    if part.get("cache_control"):
                        del part["cache_control"]
                    if part.get("type") == "text" and part.get("text") == "" and len(content) > 1:
                        continue
                    new_content.append(part)
            cleaned_msg["content"] = new_content
        elif isinstance(content, dict):
            if content.get("cache_control"):
                del content["cache_control"]

        result.append(cleaned_msg)

    return result


def extract_cache_stats(messages: list[dict[str, Any]]) -> dict[str, int]:
    """Extract cache statistics from messages.

    Args:
        messages: List of message dictionaries

    Returns:
        Dictionary with cache statistics
    """
    stats = {
        "total_messages": len(messages),
        "cached_messages": 0,
        "cached_tokens_estimate": 0,
    }

    for msg in messages:
        content = msg.get("content", [])

        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("cache_control"):
                    stats["cached_messages"] += 1
                    text = part.get("text", "")
                    stats["cached_tokens_estimate"] += len(text) // 4
        elif isinstance(content, dict) and content.get("cache_control"):
            stats["cached_messages"] += 1
            text = content.get("text", "")
            stats["cached_tokens_estimate"] += len(text) // 4

    return stats


class AnthropicCacheManager:
    """Manager for Anthropic cache operations."""

    def __init__(self, cache_threshold: float = 0.75):
        self.cache_threshold = cache_threshold

    def prepare_messages(
        self,
        messages: list[dict[str, Any]],
        enable_cache: bool = True,
    ) -> list[dict[str, Any]]:
        """Prepare messages with cache control.

        Args:
            messages: List of message dictionaries
            enable_cache: Whether to enable caching

        Returns:
            Prepared messages
        """
        if not enable_cache:
            return messages

        return apply_anthropic_cache_control(messages, self.cache_threshold)

    def extract_stats(
        self,
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Extract statistics from messages.

        Args:
            messages: List of message dictionaries

        Returns:
            Cache statistics
        """
        return extract_cache_stats(messages)

    def estimate_cost_savings(
        self,
        messages: list[dict[str, Any]],
        cache_hit_price: float = 0.00001,
        cache_miss_price: float = 0.00003,
    ) -> dict[str, float]:
        """Estimate cost savings from caching.

        Args:
            messages: List of message dictionaries
            cache_hit_price: Price per cached token
            cache_miss_price: Price per non-cached token

        Returns:
            Cost savings estimate
        """
        stats = self.extract_stats(messages)

        cached_tokens = stats["cached_tokens_estimate"]
        total_tokens = stats["cached_tokens_estimate"] * 4

        with_cache_cost = (
            cached_tokens * cache_hit_price + (total_tokens - cached_tokens) * cache_miss_price
        )
        without_cache_cost = total_tokens * cache_miss_price

        return {
            "estimated_savings": without_cache_cost - with_cache_cost,
            "with_cache": with_cache_cost,
            "without_cache": without_cache_cost,
            "cached_tokens": cached_tokens,
            "total_tokens": total_tokens,
        }


def format_cache_hint(enabled: bool = True) -> str:
    """Format a cache hint message.

    Args:
        enabled: Whether caching is enabled

    Returns:
        Formatted hint string
    """
    if enabled:
        return f"Caching enabled {CACHE_CONTROL_EMOJI}"
    return "Caching disabled"
