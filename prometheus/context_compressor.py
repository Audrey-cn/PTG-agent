#!/usr/bin/env python3
"""Prometheus 上下文压缩器."""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger("prometheus.context_compressor")


class CompressionStrategy(Enum):
    NONE = "none"
    TRUNCATE = "truncate"
    SUMMARY = "summary"
    SELECTIVE = "selective"


@dataclass
class CompressionResult:
    compressed_messages: list
    original_count: int
    compressed_count: int
    strategy: CompressionStrategy
    tokens_saved: int = 0


@dataclass
class ContextBudget:
    max_tokens: int = 100000
    max_messages: int = 1000
    reserved_tokens: int = 5000
    warning_threshold: float = 0.8

    def tokens_remaining(self) -> int:
        return self.max_tokens - self.reserved_tokens


class MessageTokenizer:
    """简单的 Token 计数器 (基于规则)"""

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        words = re.findall(r"\w+", text)
        return len(words) + len(text) // 4

    def count_messages_tokens(self, messages: list) -> int:
        total = 0
        for msg in messages:
            if isinstance(msg, dict):
                content = msg.get("content", "")
                if isinstance(content, str):
                    total += self.count_tokens(content)
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict):
                            total += self.count_tokens(part.get("text", ""))
        return total


@dataclass
class TruncationOptions:
    keep_system_prompt: bool = True
    keep_first_n_messages: int = 2
    preserve_last_turn: bool = True
    min_messages_to_keep: int = 3


@dataclass
class SelectiveRetentionOptions:
    retain_user_first: bool = True
    retain_assistant_first: bool = True
    retain_last_n_turns: int = 3
    retain_tools_results: bool = True
    retain_reasoning: bool = False


class ContextCompressor:
    """
    上下文压缩器 - 管理长对话历史的压缩和截断

    基于 Hermes 的实现，适配 Prometheus 架构。
    """

    def __init__(
        self,
        budget: ContextBudget | None = None,
        tokenizer: MessageTokenizer | None = None,
    ):
        self.budget = budget or ContextBudget()
        self.tokenizer = tokenizer or MessageTokenizer()
        self._last_compression: CompressionResult | None = None

    def estimate_messages_tokens(self, messages: list) -> int:
        """估算消息列表的 token 数量"""
        return self.tokenizer.count_messages_tokens(messages)

    def should_compress(self, messages: list) -> bool:
        """判断是否需要压缩"""
        token_count = self.estimate_messages_tokens(messages)
        return token_count > self.budget.tokens_remaining()

    def compress(
        self,
        messages: list,
        strategy: CompressionStrategy = CompressionStrategy.SELECTIVE,
        options: Any | None = None,
    ) -> CompressionResult:
        """
        压缩消息历史

        Args:
            messages: 原始消息列表
            strategy: 压缩策略
            options: 策略特定选项

        Returns:
            CompressionResult: 包含压缩结果的数据类
        """
        original_count = len(messages)
        original_tokens = self.estimate_messages_tokens(messages)

        if strategy == CompressionStrategy.NONE:
            return CompressionResult(
                compressed_messages=messages,
                original_count=original_count,
                compressed_count=len(messages),
                strategy=strategy,
            )

        elif strategy == CompressionStrategy.TRUNCATE:
            compressed = self._truncate(messages, options)
        elif strategy == CompressionStrategy.SUMMARY:
            compressed = self._summarize(messages, options)
        elif strategy == CompressionStrategy.SELECTIVE:
            compressed = self._selective_retention(messages, options)
        else:
            compressed = messages

        compressed_tokens = self.estimate_messages_tokens(compressed)
        result = CompressionResult(
            compressed_messages=compressed,
            original_count=original_count,
            compressed_count=len(compressed),
            strategy=strategy,
            tokens_saved=original_tokens - compressed_tokens,
        )
        self._last_compression = result
        return result

    def _truncate(self, messages: list, options: TruncationOptions | None) -> list:
        """截断策略 - 保留首尾消息"""
        opts = options or TruncationOptions()
        if not messages:
            return []

        result = []
        system_msgs = []
        other_msgs = []

        for msg in messages:
            if opts.keep_system_prompt and msg.get("role") == "system":
                system_msgs.append(msg)
            else:
                other_msgs.append(msg)

        result.extend(system_msgs)

        for i, msg in enumerate(other_msgs):
            if i < opts.keep_first_n_messages:
                result.append(msg)

        if opts.preserve_last_turn and len(other_msgs) > opts.keep_first_n_messages:
            last_role = None
            turn_start = len(result)
            for j in range(len(other_msgs) - 1, opts.keep_first_n_messages - 1, -1):
                msg = other_msgs[j]
                role = msg.get("role")
                if last_role is None:
                    last_role = role
                    turn_start = j
                elif role != last_role:
                    break

            for k in range(turn_start, len(other_msgs)):
                result.append(other_msgs[k])

        return result

    def _summarize(self, messages: list, options: Any | None) -> list:
        """摘要策略 - 用摘要替换中间消息"""
        if len(messages) <= 10:
            return messages

        system_msgs = [m for m in messages if m.get("role") == "system"]
        conversation_msgs = [m for m in messages if m.get("role") != "system"]

        summary_msg = {
            "role": "system",
            "content": f"[{len(conversation_msgs)} 条消息被压缩为摘要]",
        }

        return system_msgs + [summary_msg] + conversation_msgs[-6:]

    def _selective_retention(
        self, messages: list, options: SelectiveRetentionOptions | None
    ) -> list:
        """选择性保留策略"""
        opts = options or SelectiveRetentionOptions()
        if not messages:
            return []

        result = []

        user_msgs = [m for m in messages if m.get("role") == "user"]
        assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        system_msgs = [m for m in messages if m.get("role") == "system"]

        result.extend(system_msgs)

        if opts.retain_user_first and user_msgs:
            result.append(user_msgs[0])
        if opts.retain_assistant_first and assistant_msgs:
            result.append(assistant_msgs[0])

        if opts.retain_last_n_turns > 0:
            result.extend(assistant_msgs[-opts.retain_last_n_turns :])
            if len(user_msgs) >= opts.retain_last_n_turns:
                result.extend(user_msgs[-opts.retain_last_n_turns :])

        if opts.retain_tools_results:
            result.extend(tool_msgs[-10:])

        result.sort(key=lambda m: messages.index(m))

        current_tokens = self.estimate_messages_tokens(result)
        target_tokens = self.budget.tokens_remaining()

        if current_tokens > target_tokens:
            return self._truncate(result, TruncationOptions())

        return result

    def get_last_compression(self) -> CompressionResult | None:
        """获取上次压缩结果"""
        return self._last_compression

    def build_compression_context(
        self, messages: list, include_stats: bool = False
    ) -> dict[str, Any]:
        """构建压缩上下文信息"""
        result = {
            "message_count": len(messages),
            "estimated_tokens": self.estimate_messages_tokens(messages),
            "budget_remaining": self.budget.tokens_remaining(),
        }

        if include_stats and self._last_compression:
            result["last_compression"] = {
                "strategy": self._last_compression.strategy.value,
                "original_count": self._last_compression.original_count,
                "compressed_count": self._last_compression.compressed_count,
                "tokens_saved": self._last_compression.tokens_saved,
            }

        return result


_global_compressor: ContextCompressor | None = None


def get_compressor() -> ContextCompressor:
    """获取全局压缩器实例"""
    global _global_compressor
    if _global_compressor is None:
        _global_compressor = ContextCompressor()
    return _global_compressor


def compress_conversation(
    messages: list,
    strategy: CompressionStrategy = CompressionStrategy.SELECTIVE,
) -> CompressionResult:
    """快捷压缩函数"""
    compressor = get_compressor()
    return compressor.compress(messages, strategy)
