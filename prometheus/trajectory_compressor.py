#!/usr/bin/env python3
"""Prometheus Trajectory Compressor."""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

try:
    from .agent_loop import AgentConfig, AIAgent
except ImportError:
    from agent_loop import AgentConfig, AIAgent

logger = logging.getLogger("prometheus.trajectory_compressor")


@dataclass
class CompressionConfig:
    tokenizer_name: str = "gpt2"
    target_max_tokens: int = 15250
    summary_target_tokens: int = 750

    protect_first_system: bool = True
    protect_first_human: bool = True
    protect_first_gpt: bool = True
    protect_first_tool: bool = True
    protect_last_n_turns: int = 4

    summarization_model: str = "gpt-4o-mini"
    temperature: float = 0.3
    max_retries: int = 3
    retry_delay: int = 2

    add_summary_notice: bool = True
    summary_notice_text: str = (
        "\n\nSome of your previous tool responses may be summarized to preserve context."
    )
    output_suffix: str = "_compressed"

    num_workers: int = 4
    max_concurrent_requests: int = 50
    skip_under_target: bool = True
    save_over_limit: bool = True
    per_trajectory_timeout: int = 300

    metrics_enabled: bool = True
    metrics_per_trajectory: bool = True
    metrics_output_file: str = "compression_metrics.json"

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "CompressionConfig":
        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        config = cls()

        if "tokenizer" in data:
            config.tokenizer_name = data["tokenizer"].get("name", config.tokenizer_name)

        if "compression" in data:
            config.target_max_tokens = data["compression"].get(
                "target_max_tokens", config.target_max_tokens
            )
            config.summary_target_tokens = data["compression"].get(
                "summary_target_tokens", config.summary_target_tokens
            )

        if "protected_turns" in data:
            config.protect_first_system = data["protected_turns"].get(
                "first_system", config.protect_first_system
            )
            config.protect_first_human = data["protected_turns"].get(
                "first_human", config.protect_first_human
            )
            config.protect_first_gpt = data["protected_turns"].get(
                "first_gpt", config.protect_first_gpt
            )
            config.protect_first_tool = data["protected_turns"].get(
                "first_tool", config.protect_first_tool
            )
            config.protect_last_n_turns = data["protected_turns"].get(
                "last_n_turns", config.protect_last_n_turns
            )

        if "summarization" in data:
            config.summarization_model = data["summarization"].get(
                "model", config.summarization_model
            )
            config.temperature = data["summarization"].get("temperature", config.temperature)
            config.max_retries = data["summarization"].get("max_retries", config.max_retries)
            config.retry_delay = data["summarization"].get("retry_delay", config.retry_delay)

        if "output" in data:
            config.add_summary_notice = data["output"].get(
                "add_summary_notice", config.add_summary_notice
            )
            config.summary_notice_text = data["output"].get(
                "summary_notice_text", config.summary_notice_text
            )
            config.output_suffix = data["output"].get("output_suffix", config.output_suffix)

        if "processing" in data:
            config.num_workers = data["processing"].get("num_workers", config.num_workers)
            config.max_concurrent_requests = data["processing"].get(
                "max_concurrent_requests", config.max_concurrent_requests
            )
            config.skip_under_target = data["processing"].get(
                "skip_under_target", config.skip_under_target
            )
            config.save_over_limit = data["processing"].get(
                "save_over_limit", config.save_over_limit
            )

        if "metrics" in data:
            config.metrics_enabled = data["metrics"].get("enabled", config.metrics_enabled)
            config.metrics_per_trajectory = data["metrics"].get(
                "per_trajectory", config.metrics_per_trajectory
            )
            config.metrics_output_file = data["metrics"].get(
                "output_file", config.metrics_output_file
            )

        return config


@dataclass
class TrajectoryMetrics:
    original_tokens: int = 0
    compressed_tokens: int = 0
    tokens_saved: int = 0
    compression_ratio: float = 1.0

    original_turns: int = 0
    compressed_turns: int = 0
    turns_removed: int = 0

    turns_compressed_start_idx: int = -1
    turns_compressed_end_idx: int = -1
    turns_in_compressed_region: int = 0

    was_compressed: bool = False
    still_over_limit: bool = False
    skipped_under_target: bool = False

    summarization_api_calls: int = 0
    summarization_errors: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_tokens": self.original_tokens,
            "compressed_tokens": self.compressed_tokens,
            "tokens_saved": self.tokens_saved,
            "compression_ratio": round(self.compression_ratio, 4),
            "original_turns": self.original_turns,
            "compressed_turns": self.compressed_turns,
            "turns_removed": self.turns_removed,
            "compression_region": {
                "start_idx": self.turns_compressed_start_idx,
                "end_idx": self.turns_compressed_end_idx,
                "turns_count": self.turns_in_compressed_region,
            },
            "was_compressed": self.was_compressed,
            "still_over_limit": self.still_over_limit,
            "skipped_under_target": self.skipped_under_target,
            "summarization_api_calls": self.summarization_api_calls,
            "summarization_errors": self.summarization_errors,
        }


@dataclass
class AggregateMetrics:
    total_trajectories: int = 0
    trajectories_compressed: int = 0
    trajectories_skipped_under_target: int = 0
    trajectories_still_over_limit: int = 0
    trajectories_failed: int = 0

    total_tokens_before: int = 0
    total_tokens_after: int = 0
    total_tokens_saved: int = 0

    total_turns_before: int = 0
    total_turns_after: int = 0
    total_turns_removed: int = 0

    total_summarization_calls: int = 0
    total_summarization_errors: int = 0

    compression_ratios: list[float] = field(default_factory=list)
    tokens_saved_list: list[int] = field(default_factory=list)
    turns_removed_list: list[int] = field(default_factory=list)

    processing_start_time: str = ""
    processing_end_time: str = ""
    processing_duration_seconds: float = 0.0

    def add_trajectory_metrics(self, metrics: TrajectoryMetrics):
        self.total_trajectories += 1
        self.total_tokens_before += metrics.original_tokens
        self.total_tokens_after += metrics.compressed_tokens
        self.total_tokens_saved += metrics.tokens_saved
        self.total_turns_before += metrics.original_turns
        self.total_turns_after += metrics.compressed_turns
        self.total_turns_removed += metrics.turns_removed
        self.total_summarization_calls += metrics.summarization_api_calls
        self.total_summarization_errors += metrics.summarization_errors

        if metrics.was_compressed:
            self.trajectories_compressed += 1
            self.compression_ratios.append(metrics.compression_ratio)
            self.tokens_saved_list.append(metrics.tokens_saved)
            self.turns_removed_list.append(metrics.turns_removed)

        if metrics.skipped_under_target:
            self.trajectories_skipped_under_target += 1

        if metrics.still_over_limit:
            self.trajectories_still_over_limit += 1

    def to_dict(self) -> dict[str, Any]:
        avg_compression_ratio = (
            sum(self.compression_ratios) / len(self.compression_ratios)
            if self.compression_ratios
            else 1.0
        )
        avg_tokens_saved = (
            sum(self.tokens_saved_list) / len(self.tokens_saved_list)
            if self.tokens_saved_list
            else 0
        )
        avg_turns_removed = (
            sum(self.turns_removed_list) / len(self.turns_removed_list)
            if self.turns_removed_list
            else 0
        )

        return {
            "summary": {
                "total_trajectories": self.total_trajectories,
                "trajectories_compressed": self.trajectories_compressed,
                "trajectories_skipped_under_target": self.trajectories_skipped_under_target,
                "trajectories_still_over_limit": self.trajectories_still_over_limit,
                "trajectories_failed": self.trajectories_failed,
                "compression_rate": round(
                    self.trajectories_compressed / max(self.total_trajectories, 1), 4
                ),
            },
            "tokens": {
                "total_before": self.total_tokens_before,
                "total_after": self.total_tokens_after,
                "total_saved": self.total_tokens_saved,
                "overall_compression_ratio": round(
                    self.total_tokens_after / max(self.total_tokens_before, 1), 4
                ),
            },
            "turns": {
                "total_before": self.total_turns_before,
                "total_after": self.total_turns_after,
                "total_removed": self.total_turns_removed,
            },
            "averages": {
                "avg_compression_ratio": round(avg_compression_ratio, 4),
                "avg_tokens_saved_per_compressed": round(avg_tokens_saved, 1),
                "avg_turns_removed_per_compressed": round(avg_turns_removed, 2),
            },
            "summarization": {
                "total_api_calls": self.total_summarization_calls,
                "total_errors": self.total_summarization_errors,
                "success_rate": round(
                    1 - (self.total_summarization_errors / max(self.total_summarization_calls, 1)),
                    4,
                ),
            },
            "processing": {
                "start_time": self.processing_start_time,
                "end_time": self.processing_end_time,
                "duration_seconds": round(self.processing_duration_seconds, 2),
            },
        }


class TrajectoryCompressor:
    """
    压缩 Agent 轨迹以适应目标 token 预算。

    压缩策略：
    1. 保留保护的开头回合（system, human, first gpt+tool）
    2. 保留保护的结尾回合（最后 N 回合）
    3. 从可压缩的中间区域中，只压缩所需的量
    4. 用单个 human summary 消息替换压缩的回合
    5. 保持剩余的中间回合完整（模型继续使用工具）
    """

    def __init__(self, config: CompressionConfig | None = None):
        self.config = config or CompressionConfig()
        self.aggregate_metrics = AggregateMetrics()

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S",
        )
        self.logger = logging.getLogger(__name__)

    def _estimate_tokens(self, text: str) -> int:
        """估算文本的 token 数量"""
        if not text:
            return 0
        try:
            import tiktoken

            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception:
            return len(text) // 4

    def count_trajectory_tokens(self, trajectory: list[dict[str, str]]) -> int:
        """计算轨迹的总 token 数"""
        return sum(self._estimate_tokens(turn.get("value", "")) for turn in trajectory)

    def count_turn_tokens(self, trajectory: list[dict[str, str]]) -> list[int]:
        """计算每个回合的 token 数"""
        return [self._estimate_tokens(turn.get("value", "")) for turn in trajectory]

    def _find_protected_indices(self, trajectory: list[dict[str, str]]) -> tuple[set, int, int]:
        """
        找到保护回合的索引。

        返回:
            Tuple of (protected_set, compressible_start, compressible_end)
        """
        n = len(trajectory)
        protected = set()

        first_system = first_human = first_gpt = first_tool = None

        for i, turn in enumerate(trajectory):
            role = turn.get("from", "")
            if role == "system" and first_system is None:
                first_system = i
            elif role == "human" and first_human is None:
                first_human = i
            elif role == "gpt" and first_gpt is None:
                first_gpt = i
            elif role == "tool" and first_tool is None:
                first_tool = i

        if self.config.protect_first_system and first_system is not None:
            protected.add(first_system)
        if self.config.protect_first_human and first_human is not None:
            protected.add(first_human)
        if self.config.protect_first_gpt and first_gpt is not None:
            protected.add(first_gpt)
        if self.config.protect_first_tool and first_tool is not None:
            protected.add(first_tool)

        for i in range(max(0, n - self.config.protect_last_n_turns), n):
            protected.add(i)

        head_protected = [i for i in protected if i < n // 2]
        tail_protected = [i for i in protected if i >= n // 2]

        compressible_start = max(head_protected) + 1 if head_protected else 0
        compressible_end = min(tail_protected) if tail_protected else n

        return protected, compressible_start, compressible_end

    def _extract_turn_content_for_summary(
        self, trajectory: list[dict[str, str]], start: int, end: int
    ) -> str:
        """提取要摘要的回合内容"""
        parts = []
        for i in range(start, end):
            turn = trajectory[i]
            role = turn.get("from", "unknown")
            value = turn.get("value", "")

            if len(value) > 3000:
                value = value[:1500] + "\n...[truncated]...\n" + value[-500:]

            parts.append(f"[Turn {i} - {role.upper()}]:\n{value}")

        return "\n\n".join(parts)

    @staticmethod
    def _coerce_summary_content(content: Any) -> str:
        """将摘要输出规范化为字符串"""
        if not isinstance(content, str):
            content = str(content) if content else ""
        return content.strip()

    @staticmethod
    def _ensure_summary_prefix(summary: str) -> str:
        """确保摘要包含正确的前缀"""
        text = (summary or "").strip()
        if text.startswith("[CONTEXT SUMMARY]:"):
            return text
        return "[CONTEXT SUMMARY]:" if not text else f"[CONTEXT SUMMARY]: {text}"

    def _generate_summary(self, content: str, metrics: TrajectoryMetrics) -> str:
        """使用 LLM 生成摘要"""
        prompt = f"""Summarize the following agent conversation turns concisely. This summary will replace these turns in the conversation history.

Write the summary from a neutral perspective describing what the assistant did and learned. Include:
1. What actions the assistant took (tool calls, searches, file operations)
2. Key information or results obtained
3. Any important decisions or findings
4. Relevant data, file names, values, or outputs

Keep the summary factual and informative. Target approximately {self.config.summary_target_tokens} tokens.

---
TURNS TO SUMMARIZE:
{content}
---

Write only the summary, starting with "[CONTEXT SUMMARY]:" prefix."""

        for attempt in range(self.config.max_retries):
            try:
                metrics.summarization_api_calls += 1

                agent_config = AgentConfig(
                    provider="openai",
                    model=self.config.summarization_model,
                    temperature=self.config.temperature,
                )
                agent = AIAgent(config=agent_config)
                response = agent.run_conversation(prompt)

                summary = self._coerce_summary_content(response.content)
                return self._ensure_summary_prefix(summary)

            except Exception as e:
                metrics.summarization_errors += 1
                self.logger.warning(f"Summarization attempt {attempt + 1} failed: {e}")

                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (2**attempt))
                else:
                    return "[CONTEXT SUMMARY]: [Summary generation failed - previous turns contained tool calls and responses that have been compressed to save context space.]"

    async def _generate_summary_async(self, content: str, metrics: TrajectoryMetrics) -> str:
        """异步版本的摘要生成"""
        prompt = f"""Summarize the following agent conversation turns concisely. This summary will replace these turns in the conversation history.

Write the summary from a neutral perspective describing what the assistant did and learned. Include:
1. What actions the assistant took (tool calls, searches, file operations)
2. Key information or results obtained
3. Any important decisions or findings
4. Relevant data, file names, values, or outputs

Keep the summary factual and informative. Target approximately {self.config.summary_target_tokens} tokens.

---
TURNS TO SUMMARIZE:
{content}
---

Write only the summary, starting with "[CONTEXT SUMMARY]:" prefix."""

        for attempt in range(self.config.max_retries):
            try:
                metrics.summarization_api_calls += 1

                agent_config = AgentConfig(
                    provider="openai",
                    model=self.config.summarization_model,
                    temperature=self.config.temperature,
                )
                agent = AIAgent(config=agent_config)
                response = await agent.run_conversation_async(prompt)

                summary = self._coerce_summary_content(response.content)
                return self._ensure_summary_prefix(summary)

            except Exception as e:
                metrics.summarization_errors += 1
                self.logger.warning(f"Summarization attempt {attempt + 1} failed: {e}")

                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay * (2**attempt))
                else:
                    return "[CONTEXT SUMMARY]: [Summary generation failed - previous turns contained tool calls and responses that have been compressed to save context space.]"

    def compress_trajectory(
        self, trajectory: list[dict[str, str]]
    ) -> tuple[list[dict[str, str]], TrajectoryMetrics]:
        """压缩单个轨迹以适应目标 token 预算"""
        metrics = TrajectoryMetrics()
        metrics.original_turns = len(trajectory)

        turn_tokens = self.count_turn_tokens(trajectory)
        total_tokens = sum(turn_tokens)
        metrics.original_tokens = total_tokens

        if total_tokens <= self.config.target_max_tokens:
            metrics.skipped_under_target = True
            metrics.compressed_tokens = total_tokens
            metrics.compressed_turns = len(trajectory)
            metrics.compression_ratio = 1.0
            return trajectory, metrics

        protected, compress_start, compress_end = self._find_protected_indices(trajectory)

        if compress_start >= compress_end:
            metrics.compressed_tokens = total_tokens
            metrics.compressed_turns = len(trajectory)
            metrics.still_over_limit = total_tokens > self.config.target_max_tokens
            return trajectory, metrics

        tokens_to_save = total_tokens - self.config.target_max_tokens
        target_tokens_to_compress = tokens_to_save + self.config.summary_target_tokens

        accumulated_tokens = 0
        compress_until = compress_start

        for i in range(compress_start, compress_end):
            accumulated_tokens += turn_tokens[i]
            compress_until = i + 1

            if accumulated_tokens >= target_tokens_to_compress:
                break

        if accumulated_tokens < target_tokens_to_compress and compress_until < compress_end:
            compress_until = compress_end
            accumulated_tokens = sum(turn_tokens[compress_start:compress_end])

        metrics.turns_compressed_start_idx = compress_start
        metrics.turns_compressed_end_idx = compress_until
        metrics.turns_in_compressed_region = compress_until - compress_start

        content_to_summarize = self._extract_turn_content_for_summary(
            trajectory, compress_start, compress_until
        )

        summary = self._generate_summary(content_to_summarize, metrics)

        compressed = []

        for i in range(compress_start):
            turn = trajectory[i].copy()
            if turn.get("from") == "system" and self.config.add_summary_notice:
                turn["value"] = turn["value"] + self.config.summary_notice_text
            compressed.append(turn)

        compressed.append({"from": "human", "value": summary})

        for i in range(compress_until, len(trajectory)):
            compressed.append(trajectory[i].copy())

        metrics.compressed_turns = len(compressed)
        metrics.compressed_tokens = self.count_trajectory_tokens(compressed)
        metrics.turns_removed = metrics.original_turns - metrics.compressed_turns
        metrics.tokens_saved = metrics.original_tokens - metrics.compressed_tokens
        metrics.compression_ratio = metrics.compressed_tokens / max(metrics.original_tokens, 1)
        metrics.was_compressed = True
        metrics.still_over_limit = metrics.compressed_tokens > self.config.target_max_tokens

        return compressed, metrics

    async def compress_trajectory_async(
        self, trajectory: list[dict[str, str]]
    ) -> tuple[list[dict[str, str]], TrajectoryMetrics]:
        """异步版本的轨迹压缩"""
        metrics = TrajectoryMetrics()
        metrics.original_turns = len(trajectory)

        turn_tokens = self.count_turn_tokens(trajectory)
        total_tokens = sum(turn_tokens)
        metrics.original_tokens = total_tokens

        if total_tokens <= self.config.target_max_tokens:
            metrics.skipped_under_target = True
            metrics.compressed_tokens = total_tokens
            metrics.compressed_turns = len(trajectory)
            metrics.compression_ratio = 1.0
            return trajectory, metrics

        protected, compress_start, compress_end = self._find_protected_indices(trajectory)

        if compress_start >= compress_end:
            metrics.compressed_tokens = total_tokens
            metrics.compressed_turns = len(trajectory)
            metrics.still_over_limit = total_tokens > self.config.target_max_tokens
            return trajectory, metrics

        tokens_to_save = total_tokens - self.config.target_max_tokens
        target_tokens_to_compress = tokens_to_save + self.config.summary_target_tokens

        accumulated_tokens = 0
        compress_until = compress_start

        for i in range(compress_start, compress_end):
            accumulated_tokens += turn_tokens[i]
            compress_until = i + 1
            if accumulated_tokens >= target_tokens_to_compress:
                break

        if accumulated_tokens < target_tokens_to_compress and compress_until < compress_end:
            compress_until = compress_end
            accumulated_tokens = sum(turn_tokens[compress_start:compress_end])

        metrics.turns_compressed_start_idx = compress_start
        metrics.turns_compressed_end_idx = compress_until
        metrics.turns_in_compressed_region = compress_until - compress_start

        content_to_summarize = self._extract_turn_content_for_summary(
            trajectory, compress_start, compress_until
        )

        summary = await self._generate_summary_async(content_to_summarize, metrics)

        compressed = []

        for i in range(compress_start):
            turn = trajectory[i].copy()
            if turn.get("from") == "system" and self.config.add_summary_notice:
                turn["value"] = turn["value"] + self.config.summary_notice_text
            compressed.append(turn)

        compressed.append({"from": "human", "value": summary})

        for i in range(compress_until, len(trajectory)):
            compressed.append(trajectory[i].copy())

        metrics.compressed_turns = len(compressed)
        metrics.compressed_tokens = self.count_trajectory_tokens(compressed)
        metrics.turns_removed = metrics.original_turns - metrics.compressed_turns
        metrics.tokens_saved = metrics.original_tokens - metrics.compressed_tokens
        metrics.compression_ratio = metrics.compressed_tokens / max(metrics.original_tokens, 1)
        metrics.was_compressed = True
        metrics.still_over_limit = metrics.compressed_tokens > self.config.target_max_tokens

        return compressed, metrics

    def process_entry(self, entry: dict[str, Any]) -> tuple[dict[str, Any], TrajectoryMetrics]:
        """处理单个 JSONL 条目"""
        if "conversations" not in entry:
            metrics = TrajectoryMetrics()
            return entry, metrics

        trajectory = entry["conversations"]
        compressed_trajectory, metrics = self.compress_trajectory(trajectory)

        result = entry.copy()
        result["conversations"] = compressed_trajectory

        if self.config.metrics_per_trajectory and metrics.was_compressed:
            result["compression_metrics"] = metrics.to_dict()

        return result, metrics

    async def process_entry_async(
        self, entry: dict[str, Any]
    ) -> tuple[dict[str, Any], TrajectoryMetrics]:
        """异步版本的条目处理"""
        if "conversations" not in entry:
            metrics = TrajectoryMetrics()
            return entry, metrics

        trajectory = entry["conversations"]
        compressed_trajectory, metrics = await self.compress_trajectory_async(trajectory)

        result = entry.copy()
        result["conversations"] = compressed_trajectory

        if self.config.metrics_per_trajectory and metrics.was_compressed:
            result["compression_metrics"] = metrics.to_dict()

        return result, metrics

    def process_directory(self, input_dir: Path, output_dir: Path):
        """处理目录中的所有 JSONL 文件"""
        asyncio.run(self._process_directory_async(input_dir, output_dir))

    async def _process_directory_async(self, input_dir: Path, output_dir: Path):
        """异步版本的目录处理"""
        self.aggregate_metrics.processing_start_time = datetime.now().isoformat()
        start_time = time.time()

        jsonl_files = sorted(input_dir.glob("*.jsonl"))

        if not jsonl_files:
            self.logger.warning(f"No JSONL files found in {input_dir}")
            return

        all_entries = []

        for file_path in jsonl_files:
            with open(file_path, encoding="utf-8") as f:
                for line_num, line in enumerate(f):
                    line = line.strip()
                    if line:
                        try:
                            entry = json.loads(line)
                            all_entries.append((file_path, line_num, entry))
                        except json.JSONDecodeError as e:
                            self.logger.warning(
                                f"Skipping invalid JSON at {file_path}:{line_num}: {e}"
                            )

        total_entries = len(all_entries)

        print(f"\n{'=' * 60}")
        print(f"📂 Input: {input_dir}")
        print(f"📂 Output: {output_dir}")
        print(f"📄 Files to process: {len(jsonl_files)}")
        print(f"📊 Total trajectories: {total_entries:,}")
        print(f"🎯 Target max tokens: {self.config.target_max_tokens:,}")
        print(f"📝 Summary target tokens: {self.config.summary_target_tokens}")
        print(f"⚡ Max concurrent API calls: {self.config.max_concurrent_requests}")
        print(f"{'=' * 60}\n")

        semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)
        progress_lock = asyncio.Lock()
        compressed_count = 0
        skipped_count = 0
        api_calls = 0
        in_flight = 0
        timeout_count = 0

        results = {f: {} for f in jsonl_files}

        async def process_single(file_path: Path, entry_idx: int, entry: dict):
            nonlocal compressed_count, skipped_count, api_calls, in_flight, timeout_count

            async with semaphore:
                async with progress_lock:
                    in_flight += 1

                try:
                    processed_entry, metrics = await asyncio.wait_for(
                        self.process_entry_async(entry), timeout=self.config.per_trajectory_timeout
                    )
                    results[file_path][entry_idx] = (processed_entry, metrics)

                    async with progress_lock:
                        self.aggregate_metrics.add_trajectory_metrics(metrics)

                        if metrics.was_compressed:
                            compressed_count += 1
                            api_calls += metrics.summarization_api_calls
                        if metrics.skipped_under_target:
                            skipped_count += 1

                        in_flight -= 1

                        print(
                            f"\rProgress: {len([r for f in results.values() for r in f.values() if r is not None])}/{total_entries} "
                            f"| Compressed: {compressed_count} | Skipped: {skipped_count} | "
                            f"API calls: {api_calls} | In-flight: {in_flight}",
                            end="",
                        )

                except TimeoutError:
                    self.logger.warning(f"Timeout processing entry from {file_path}:{entry_idx}")

                    async with progress_lock:
                        self.aggregate_metrics.trajectories_failed += 1
                        timeout_count += 1
                        in_flight -= 1

                    results[file_path][entry_idx] = None

                except Exception as e:
                    self.logger.error(f"Error processing entry from {file_path}:{entry_idx}: {e}")

                    async with progress_lock:
                        self.aggregate_metrics.trajectories_failed += 1
                        in_flight -= 1

                    results[file_path][entry_idx] = (entry, TrajectoryMetrics())

        tasks = [
            process_single(file_path, entry_idx, entry)
            for file_path, entry_idx, entry in all_entries
        ]

        await asyncio.gather(*tasks)

        output_dir.mkdir(parents=True, exist_ok=True)

        for file_path in jsonl_files:
            output_path = output_dir / file_path.name
            file_results = results[file_path]

            sorted_entries = [
                file_results[idx][0]
                for idx in sorted(file_results.keys())
                if file_results[idx] is not None
            ]

            with open(output_path, "w", encoding="utf-8") as f:
                for entry in sorted_entries:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        self.aggregate_metrics.processing_end_time = datetime.now().isoformat()
        self.aggregate_metrics.processing_duration_seconds = time.time() - start_time

        self._print_summary()

        if self.config.metrics_enabled:
            metrics_path = output_dir / self.config.metrics_output_file
            with open(metrics_path, "w") as f:
                json.dump(self.aggregate_metrics.to_dict(), f, indent=2)
            print(f"\n💾 Metrics saved to {metrics_path}")

    def _print_summary(self):
        """打印压缩统计摘要"""
        m = self.aggregate_metrics.to_dict()

        total = m["summary"]["total_trajectories"]
        compressed = m["summary"]["trajectories_compressed"]
        skipped = m["summary"]["trajectories_skipped_under_target"]
        over_limit = m["summary"]["trajectories_still_over_limit"]
        failed = m["summary"]["trajectories_failed"]

        tokens_before = m["tokens"]["total_before"]
        tokens_after = m["tokens"]["total_after"]
        tokens_saved = m["tokens"]["total_saved"]

        compressed_pct = (compressed / max(total, 1)) * 100
        skipped_pct = (skipped / max(total, 1)) * 100

        print(f"\n{'=' * 60}")
        print("📊 COMPRESSION SUMMARY")
        print(f"{'=' * 60}")
        print(f"Total trajectories:        {total:>12,}")
        print(f"Compressed:                {compressed:>12,} ({compressed_pct:>5.1f}%)")
        print(f"Skipped (under target):    {skipped:>12,} ({skipped_pct:>5.1f}%)")
        print(f"Still over limit:          {over_limit:>12,}")
        print(f"Failed:                    {failed:>12,}")
        print("-" * 60)
        print(f"Total tokens before:       {tokens_before:>12,}")
        print(f"Total tokens after:        {tokens_after:>12,}")
        print(f"Total tokens saved:        {tokens_saved:>12,}")
        print(f"Overall compression ratio: {m['tokens']['overall_compression_ratio']:>10.4f}")
        print("-" * 60)
        print(f"Processing time:           {m['processing']['duration_seconds']:>10.2f}s")
        print(f"{'=' * 60}")
