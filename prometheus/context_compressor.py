from __future__ import annotations

import json
import copy
from typing import Optional


def compress_history(
    history: list[dict],
    focus: Optional[str] = None,
    max_messages: int = 20,
    keep_recent: int = 6,
) -> list[dict]:
    if len(history) <= max_messages:
        return history

    recent = history[-keep_recent:] if keep_recent < len(history) else history
    older = history[:-keep_recent] if keep_recent < len(history) else []

    if not older:
        return history

    summary_parts = []
    for msg in older:
        role = msg.get("role", "?")
        content = msg.get("content", "")
        if role == "user":
            summary_parts.append(f"User: {content[:200]}")
        elif role == "assistant":
            summary_parts.append(f"Assistant: {content[:200]}")

    summary_text = "\n".join(summary_parts)
    if focus:
        summary = (
            f"[Earlier conversation summary (focus: {focus})]\n"
            f"{summary_text}\n[End of summary]"
        )
    else:
        summary = (
            f"[Earlier conversation summary - {len(older)} messages compressed]\n"
            f"{summary_text}\n[End of summary]"
        )

    compressed = [{"role": "system", "content": summary}]
    compressed.extend(recent)
    return compressed


def estimate_tokens(messages: list[dict]) -> int:
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        total += len(content)
        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                total += len(json.dumps(tc, ensure_ascii=False))
    return total // 4


def should_compress(messages: list[dict], threshold: int = 80000) -> bool:
    return estimate_tokens(messages) > threshold


def auto_compress(messages: list[dict], target_tokens: int = 60000) -> list[dict]:
    if estimate_tokens(messages) <= target_tokens:
        return messages

    keep_recent = 6
    while keep_recent < len(messages):
        compressed = compress_history(messages, max_messages=len(messages), keep_recent=keep_recent)
        if estimate_tokens(compressed) <= target_tokens:
            return compressed
        keep_recent += 2

    return messages[-keep_recent:]
