#!/usr/bin/env python3
"""Prometheus BatchRunner - 批量任务处理器."""

import concurrent.futures
import json
import logging
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
    from .agent_loop import AgentConfig, AgentResponse, AIAgent
except ImportError:
    from agent_loop import AgentConfig, AIAgent

logger = logging.getLogger("prometheus.batch_runner")


@dataclass
class BatchTask:
    id: str
    input: str
    system_prompt: str = ""
    metadata: dict = field(default_factory=dict)
    status: str = "pending"
    result: str | None = None
    error: str | None = None
    duration_ms: float = 0
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class BatchResult:
    batch_id: str
    total: int
    succeeded: int
    failed: int
    total_duration_ms: float
    results: list[BatchTask]
    started_at: str
    completed_at: str
    errors: list[dict] = field(default_factory=list)


class BatchRunner:
    """
    批量任务运行器

    特性:
    - 并行/串行执行
    - 进度跟踪
    - 错误处理
    - 结果聚合
    - 超时控制
    """

    def __init__(
        self,
        max_workers: int = 4,
        max_retries: int = 2,
        timeout_per_task: int = 300,
        save_dir: Path | None = None,
    ):
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.timeout_per_task = timeout_per_task
        self.save_dir = save_dir or Path.home() / ".prometheus" / "batch_runs"
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        tasks: list[BatchTask],
        agent_config: AgentConfig,
        parallel: bool = True,
        progress_callback: Callable[[int, int, BatchTask], None] = None,
    ) -> BatchResult:
        """
        执行批量任务

        Args:
            tasks: 任务列表
            agent_config: Agent 配置
            parallel: 是否并行执行
            progress_callback: 进度回调 (completed, total, current_task)

        Returns:
            BatchResult: 批量执行结果
        """
        batch_id = str(uuid.uuid4())[:8]
        started_at = datetime.now().isoformat()
        start_time = time.time()

        results: list[BatchTask] = []
        errors: list[dict] = []
        completed = 0
        total = len(tasks)
        lock = threading.Lock()

        def execute_task(task: BatchTask) -> BatchTask:
            nonlocal completed
            task.status = "running"
            task.started_at = datetime.now().isoformat()

            for attempt in range(self.max_retries + 1):
                try:
                    agent = AIAgent(config=agent_config, system_prompt=task.system_prompt)

                    task_start = time.time()
                    response = agent.run_conversation(task.input)
                    task.duration_ms = (time.time() - task_start) * 1000

                    if response.finish_reason == "error":
                        raise Exception(f"Agent error: {response.content}")

                    task.result = response.content
                    task.status = "completed"
                    break

                except Exception as e:
                    if attempt < self.max_retries:
                        time.sleep(2**attempt)
                        continue
                    task.error = str(e)
                    task.status = "failed"

            task.completed_at = datetime.now().isoformat()

            with lock:
                completed += 1
                if progress_callback:
                    try:
                        progress_callback(completed, total, task)
                    except Exception as e:
                        logger.warning(f"Progress callback failed: {e}")

            return task

        if parallel and len(tasks) > 1:
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {executor.submit(execute_task, task): task for task in tasks}
                for future in concurrent.futures.as_completed(
                    futures, timeout=self.timeout_per_task * len(tasks)
                ):
                    try:
                        result = future.result()
                        results.append(result)
                        if result.status == "failed":
                            errors.append(
                                {
                                    "task_id": result.id,
                                    "error": result.error,
                                }
                            )
                    except Exception as e:
                        task = futures[future]
                        task.status = "failed"
                        task.error = str(e)
                        results.append(task)
                        errors.append({"task_id": task.id, "error": str(e)})
        else:
            for task in tasks:
                result = execute_task(task)
                results.append(result)
                if result.status == "failed":
                    errors.append({"task_id": result.id, "error": result.error})

        total_duration_ms = (time.time() - start_time) * 1000
        succeeded = sum(1 for r in results if r.status == "completed")
        failed = total - succeeded

        batch_result = BatchResult(
            batch_id=batch_id,
            total=total,
            succeeded=succeeded,
            failed=failed,
            total_duration_ms=total_duration_ms,
            results=results,
            started_at=started_at,
            completed_at=datetime.now().isoformat(),
            errors=errors,
        )

        self._save_result(batch_result)

        return batch_result

    def _save_result(self, result: BatchResult):
        """保存结果到文件"""
        filepath = self.save_dir / f"batch_{result.batch_id}.json"
        data = {
            "batch_id": result.batch_id,
            "total": result.total,
            "succeeded": result.succeeded,
            "failed": result.failed,
            "total_duration_ms": result.total_duration_ms,
            "started_at": result.started_at,
            "completed_at": result.completed_at,
            "errors": result.errors,
            "results": [
                {
                    "id": r.id,
                    "input": r.input[:500],
                    "status": r.status,
                    "result": r.result[:1000] if r.result else None,
                    "error": r.error,
                    "duration_ms": r.duration_ms,
                    "metadata": r.metadata,
                }
                for r in result.results
            ],
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Batch result saved to {filepath}")


def create_batch_from_file(
    filepath: str,
    input_key: str = "input",
    system_prompt_key: str = "system_prompt",
    metadata_keys: list[str] = None,
) -> list[BatchTask]:
    """
    从 JSON/JSONL 文件创建批量任务

    Args:
        filepath: 文件路径
        input_key: 输入字段名
        system_prompt_key: system prompt 字段名
        metadata_keys: 要保留为 metadata 的字段

    Returns:
        List[BatchTask]: 任务列表
    """
    tasks = []
    path = Path(filepath)

    if path.suffix == ".jsonl":
        with open(path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                if line.strip():
                    try:
                        data = json.loads(line)
                        task = BatchTask(
                            id=data.get("id", f"{path.stem}_{line_num}"),
                            input=data.get(input_key, ""),
                            system_prompt=data.get(system_prompt_key, ""),
                            metadata={k: data[k] for k in (metadata_keys or []) if k in data},
                        )
                        tasks.append(task)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse line {line_num}: {e}")
    elif path.suffix == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            for i, item in enumerate(data):
                task = BatchTask(
                    id=item.get("id", f"{path.stem}_{i}"),
                    input=item.get(input_key, ""),
                    system_prompt=item.get(system_prompt_key, ""),
                    metadata={k: item[k] for k in (metadata_keys or []) if k in item},
                )
                tasks.append(task)
        else:
            raise ValueError("JSON file must contain an array of tasks")
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}")

    return tasks


def run_batch_from_file(
    filepath: str,
    agent_config: AgentConfig,
    max_workers: int = 4,
    parallel: bool = True,
) -> BatchResult:
    """从文件创建并运行批量任务的便捷函数"""
    runner = BatchRunner(max_workers=max_workers)
    tasks = create_batch_from_file(filepath)
    return runner.run(tasks, agent_config, parallel=parallel)
