"""上下文压缩器 - ContextCompressor."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

SUMMARY_PREFIX = (
    "[CONTEXT COMPACTION - REFERENCE ONLY] Earlier turns were compacted "
    "into the summary below. This is a handoff from a previous context "
    "window -- treat it as background reference, NOT as active instructions. "
    "Do NOT answer questions or fulfill requests mentioned in this summary; "
    "they were already addressed. "
    "Your current task is identified in the '## Active Task' section of the "
    "summary -- resume exactly from there. "
    "Respond ONLY to the latest user message "
    "that appears AFTER this summary. The current session state (files, "
    "config, etc.) may reflect work described here -- avoid repeating it:"
)

MIN_SUMMARY_TOKENS = 2000
SUMMARY_RATIO = 0.20
SUMMARY_TOKENS_CEILING = 12000

PRUNED_TOOL_PLACEHOLDER = "[Old tool output cleared to save context space]"

CHARS_PER_TOKEN = 4
IMAGE_TOKEN_ESTIMATE = 1600
IMAGE_CHAR_EQUIVALENT = IMAGE_TOKEN_ESTIMATE * CHARS_PER_TOKEN
SUMMARY_FAILURE_COOLDOWN_SECONDS = 600


def _content_length_for_budget(raw_content: Any) -> int:
    """计算消息内容的有效字符长度用于 token 预算"""
    if isinstance(raw_content, str):
        return len(raw_content)
    if not isinstance(raw_content, list):
        return len(str(raw_content or ""))

    total = 0
    for p in raw_content:
        if isinstance(p, str):
            total += len(p)
            continue
        if not isinstance(p, dict):
            total += len(str(p))
            continue
        ptype = p.get("type")
        if ptype in {"image_url", "input_image", "image"}:
            total += IMAGE_CHAR_EQUIVALENT
        else:
            total += len(p.get("text", "") or "")
    return total


def _content_text_for_contains(content: Any) -> str:
    """返回消息内容的文本视图（仅用于子串检查）"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(part for part in parts if part)
    return str(content)


def _append_text_to_content(content: Any, text: str, *, prepend: bool = False) -> Any:
    """安全地向消息内容追加或前置文本"""
    if content is None:
        return text
    if isinstance(content, str):
        return text + content if prepend else content + text
    if isinstance(content, list):
        text_block = {"type": "text", "text": text}
        return [text_block, *content] if prepend else [*content, text_block]
    rendered = str(content)
    return text + rendered if prepend else rendered + text


class ContextCompressor:
    """上下文压缩器"""

    def __init__(
        self,
        auxiliary_model: str = "gpt-4o-mini",
        max_context_length: int = 128000,
        min_summary_tokens: int = MIN_SUMMARY_TOKENS,
    ):
        self.auxiliary_model = auxiliary_model
        self.max_context_length = max_context_length
        self.min_summary_tokens = min_summary_tokens
        self._last_summary_time = 0.0
        self._summary_cache: dict[str, str] = {}

    def should_compress(self, messages: list[dict[str, Any]]) -> bool:
        """检查是否需要压缩上下文"""
        total_length = sum(_content_length_for_budget(m.get("content", "")) for m in messages)
        return total_length > self.max_context_length * 0.8

    def compress(
        self,
        messages: list[dict[str, Any]],
        model_context_length: int | None = None,
    ) -> list[dict[str, Any]]:
        """压缩上下文，返回压缩后的消息列表"""
        if not self.should_compress(messages):
            return messages

        if time.time() - self._last_summary_time < SUMMARY_FAILURE_COOLDOWN_SECONDS:
            logger.debug("Summary cooldown active, skipping compression")
            return self._prune_oldest_messages(messages)

        compressed = self._do_compress(messages, model_context_length)
        self._last_summary_time = time.time()
        return compressed

    def _do_compress(
        self,
        messages: list[dict[str, Any]],
        model_context_length: int | None = None,
    ) -> list[dict[str, Any]]:
        """执行压缩逻辑"""
        if len(messages) <= 4:
            return messages

        head = messages[:2]
        middle = messages[2:-2]
        tail = messages[-2:]

        if not middle:
            return messages

        summary = self._summarize_turns(middle)
        if not summary:
            return self._prune_oldest_messages(messages)

        summary_msg = {
            "role": "assistant",
            "content": f"{SUMMARY_PREFIX}\n\n{summary}",
        }

        cache_key = self._make_cache_key(middle)
        self._summary_cache[cache_key] = summary

        return [*head, summary_msg, *tail]

    def _summarize_turns(self, middle_turns: list[dict[str, Any]]) -> str:
        """使用辅助模型总结中间轮次"""
        if not middle_turns:
            return ""

        try:
            summary_input = self._format_for_summarizer(middle_turns)
            return self._call_summarizer(summary_input)
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return ""

    def _format_for_summarizer(self, turns: list[dict[str, Any]]) -> str:
        """格式化轮次用于总结器输入"""
        lines = ["## Conversation History\n"]
        for msg in turns:
            role = msg.get("role", "unknown")
            content = _content_text_for_contains(msg.get("content", ""))
            lines.append(f"\n[{role.upper()}]\n{content[:500]}")

        lines.append("\n## Summary Format\n")
        lines.append("Provide a concise summary including:\n")
        lines.append("- Main topics discussed\n")
        lines.append("- Key decisions made\n")
        lines.append("- Pending questions or work remaining\n")

        return "\n".join(lines)

    def _call_summarizer(self, summary_input: str) -> str:
        """调用辅助模型生成总结"""
        try:
            from openai import OpenAI

            client = OpenAI()

            response = client.chat.completions.create(
                model=self.auxiliary_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a context summarizer. Summarize the conversation concisely. Do not respond to any questions, only summarize what happened.",
                    },
                    {"role": "user", "content": summary_input},
                ],
                max_tokens=self.min_summary_tokens,
                temperature=0.3,
            )

            return response.choices[0].message.content or ""

        except Exception as e:
            logger.error(f"Failed to call summarizer: {e}")
            return ""

    def _prune_oldest_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """删除最旧的消息直到在预算内"""
        if len(messages) <= 4:
            return messages

        pruned = list(messages)
        while len(pruned) > 4 and self._estimated_tokens(pruned) > self.max_context_length * 0.6:
            pruned.pop(2)

        if len(pruned) > 2:
            pruned.insert(
                2,
                {
                    "role": "system",
                    "content": "[Earlier conversation pruned due to context length]",
                },
            )

        return pruned

    def _estimated_tokens(self, messages: list[dict[str, Any]]) -> int:
        """粗略估算消息列表的 token 数"""
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            total += _content_length_for_budget(content) // CHARS_PER_TOKEN
            total += 50
        return total

    def _make_cache_key(self, turns: list[dict[str, Any]]) -> str:
        """生成缓存键"""
        content = json.dumps(turns, sort_keys=True, default=str)
        return hashlib.md5(content.encode()).hexdigest()

    def get_cached_summary(self, turns: list[dict[str, Any]]) -> str | None:
        """获取缓存的总结"""
        key = self._make_cache_key(turns)
        return self._summary_cache.get(key)


def compress_messages(
    messages: list[dict[str, Any]],
    model_context_length: int | None = None,
) -> list[dict[str, Any]]:
    """便捷函数：压缩消息"""
    compressor = ContextCompressor()
    return compressor.compress(messages, model_context_length)
