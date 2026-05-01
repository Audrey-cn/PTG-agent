"""🔥 普罗米修斯编排者 — Prometheus Orchestrator."""

from __future__ import annotations

import enum
import json
import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from prometheus.environments.agent_loop import AgentResult, PrometheusAgentLoop

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONCURRENT_CHILDREN = 3
DEFAULT_CHILD_TIMEOUT = 600
DEFAULT_MAX_ITERATIONS = 50
MAX_DEPTH = 1
_MIN_SPAWN_DEPTH = 1
_MAX_SPAWN_DEPTH_CAP = 3
_BLOCKED_TOOLS = frozenset(
    {
        "delegate_task",
        "clarify",
        "memory",
        "send_message",
        "execute_code",
    }
)


@dataclass
class SubagentRecord:
    """子 Agent 记录"""

    subagent_id: str
    parent_id: str | None
    depth: int
    goal: str
    model: str | None
    started_at: float = field(default_factory=time.time)
    tool_count: int = 0
    status: str = "running"
    workspace_path: str | None = None
    role: str = "leaf"
    agent: Any | None = None


class DelegateEvent(enum.StrEnum):
    """委托进度事件类型"""

    TASK_SPAWNED = "delegate.task_spawned"
    TASK_PROGRESS = "delegate.task_progress"
    TASK_COMPLETED = "delegate.task_completed"
    TASK_FAILED = "delegate.task_failed"
    TASK_THINKING = "delegate.task_thinking"
    TASK_TOOL_STARTED = "delegate.task_started"
    TASK_TOOL_COMPLETED = "delegate.tool_completed"


_spawn_pause_lock = threading.Lock()
_spawn_paused: bool = False

_active_subagents_lock = threading.Lock()
_active_subagents: dict[str, dict[str, Any]] = {}

_coord_dir = Path("/tmp/prometheus-coordination")
_coord_dir.mkdir(exist_ok=True, parents=True)


def set_spawn_paused(paused: bool) -> bool:
    """全局暂停/恢复子 Agent 生成"""
    global _spawn_paused
    with _spawn_pause_lock:
        _spawn_paused = bool(paused)
        return _spawn_paused


def is_spawn_paused() -> bool:
    """检查是否暂停"""
    with _spawn_pause_lock:
        return _spawn_paused


def _register_subagent(record: dict[str, Any]) -> None:
    """注册子 Agent"""
    sid = record.get("subagent_id")
    if not sid:
        return
    with _active_subagents_lock:
        _active_subagents[sid] = record


def _unregister_subagent(subagent_id: str) -> None:
    """注销子 Agent"""
    with _active_subagents_lock:
        _active_subagents.pop(subagent_id, None)


def interrupt_subagent(subagent_id: str) -> bool:
    """请求单个子 Agent 在下一个迭代边界停止"""
    with _active_subagents_lock:
        record = _active_subagents.get(subagent_id)
    if not record:
        return False
    agent = record.get("agent")
    if agent is None:
        return False
    try:
        if hasattr(agent, "interrupt"):
            agent.interrupt(f"Interrupted via Prometheus ({subagent_id})")
    except Exception as exc:
        logger.debug("interrupt_subagent(%s) failed: %s", subagent_id, exc)
        return False
    return True


def list_active_subagents() -> list[dict[str, Any]]:
    """获取当前运行的子 Agent 树快照"""
    with _active_subagents_lock:
        return [{k: v for k, v in r.items() if k != "agent"} for r in _active_subagents.values()]


class PrometheusOrchestrator:
    """普罗米修斯编排者"""

    def __init__(
        self,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT_CHILDREN,
        max_depth: int = MAX_DEPTH,
        child_timeout: float = DEFAULT_CHILD_TIMEOUT,
    ):
        self.max_concurrent = max_concurrent
        self.max_depth = max_depth
        self.child_timeout = child_timeout
        self._coordinator_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def spawn(
        self,
        goal: str,
        context: str | None = None,
        parent_id: str | None = None,
        depth: int = 1,
        role: str = "leaf",
        model: str | None = None,
        workspace_path: str | None = None,
        toolset: list[str] | None = None,
    ) -> str:
        """派生子 Agent"""
        if is_spawn_paused():
            raise RuntimeError("Subagent spawning is paused")

        if depth >= self.max_depth:
            raise RuntimeError(f"Max spawn depth {self.max_depth} reached")

        subagent_id = str(uuid.uuid4())

        record = SubagentRecord(
            subagent_id=subagent_id,
            parent_id=parent_id,
            depth=depth,
            goal=goal,
            model=model,
            workspace_path=workspace_path or os.getcwd(),
            role=role,
            status="spawning",
        )

        _register_subagent(record)

        thread = threading.Thread(
            target=self._run_single_child,
            args=(subagent_id, goal, context, depth, role, workspace_path, toolset),
            daemon=True,
        )
        thread.start()

        return subagent_id

    def _run_single_child(
        self,
        subagent_id: str,
        goal: str,
        context: str | None,
        depth: int,
        role: str,
        workspace_path: str | None,
        toolset: list[str] | None,
    ) -> None:
        """在独立线程中运行单个子 Agent"""
        try:
            with _active_subagents_lock:
                record = _active_subagents.get(subagent_id)
                if record:
                    record["status"] = "running"

            messages = [
                {
                    "role": "system",
                    "content": self._build_child_system_prompt(
                        goal, context, workspace_path, role, depth
                    ),
                },
                {"role": "user", "content": goal},
            ]

            logger.info(f"[{subagent_id[:8]}] Child agent spawned: {goal[:50]}...")

            result = self._run_child_agent(subagent_id, messages, toolset)

            with _active_subagents_lock:
                record = _active_subagents.get(subagent_id)
                if record:
                    record["status"] = "completed" if result.finished_naturally else "failed"
                    record["result"] = {
                        "finished_naturally": result.finished_naturally,
                        "turns_used": result.turns_used,
                        "messages_count": len(result.messages),
                    }

            self._save_coordination_state(subagent_id, result)

        except Exception as exc:
            logger.error(f"[{subagent_id[:8]}] Child agent failed: {exc}")
            with _active_subagents_lock:
                record = _active_subagents.get(subagent_id)
                if record:
                    record["status"] = "failed"
                    record["error"] = str(exc)
        finally:
            _unregister_subagent(subagent_id)

    def _run_child_agent(
        self,
        subagent_id: str,
        messages: list[dict[str, Any]],
        toolset: list[str] | None,
    ) -> AgentResult:
        """运行子 Agent（简化版本）"""
        from prometheus.toolsets import resolve_toolset

        if toolset is None:
            toolset = ["terminal", "file", "web"]

        tool_names = set()
        for ts_name in toolset:
            tools = resolve_toolset(ts_name)
            tool_names.update(tools)

        for blocked in _BLOCKED_TOOLS:
            tool_names.discard(blocked)

        tool_schemas = []
        for name in tool_names:
            from prometheus.tools.registry import registry

            tool_def = registry.get_tool_definition(name)
            if tool_def:
                tool_schemas.append(tool_def)

        class FakeServer:
            def __init__(self):
                self.model = "gpt-4o"

            async def chat_completion(self, **kwargs):
                import asyncio

                await asyncio.sleep(0.1)

                class Choice:
                    def __init__(self):
                        self.message = type(
                            "obj", (object,), {"content": "Task completed", "tool_calls": None}
                        )()

                class Response:
                    def __init__(self):
                        self.choices = [Choice()]

                return Response()

        agent = PrometheusAgentLoop(
            server=FakeServer(),
            tool_schemas=tool_schemas,
            valid_tool_names=tool_names,
            max_turns=DEFAULT_MAX_ITERATIONS,
        )

        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(agent.run(messages))
        finally:
            loop.close()

    def _build_child_system_prompt(
        self,
        goal: str,
        context: str | None,
        workspace_path: str | None,
        role: str,
        depth: int,
    ) -> str:
        """构建子 Agent 系统提示"""
        parts = [
            "You are a focused Prometheus subagent working on a specific delegated task.",
            "",
            f"YOUR TASK:\n{goal}",
        ]

        if context and context.strip():
            parts.append(f"\nCONTEXT:\n{context}")

        if workspace_path:
            parts.append(
                f"\nWORKSPACE PATH:\n{workspace_path}\n"
                "Use this exact path for local operations unless the task explicitly says otherwise."
            )

        parts.append(
            "\nComplete this task using the tools available to you. "
            "When finished, provide a clear, concise summary of:\n"
            "- What you did\n"
            "- What you found or accomplished\n"
            "- Any files you created or modified\n"
            "- Any issues encountered\n\n"
            "Be thorough but concise -- your response is returned to the parent agent as a summary."
        )

        if role == "orchestrator" and depth < self.max_depth - 1:
            parts.append(
                "\n## Subagent Spawning (Orchestrator Role)\n"
                "You have access to the `delegate_task` tool and CAN spawn "
                "your own subagents to parallelize independent work.\n\n"
                "WHEN to delegate:\n"
                "- The goal decomposes into 2+ independent subtasks that can run in parallel.\n"
                "- A subtask is reasoning-heavy and would flood your context.\n\n"
                "WHEN NOT to delegate:\n"
                "- Single-step mechanical work.\n"
                "- Trivial tasks you can execute in one or two tool calls.\n"
            )

        return "\n".join(parts)

    def _save_coordination_state(self, subagent_id: str, result: AgentResult) -> None:
        """保存协调状态到文件"""
        try:
            state_file = _coord_dir / f"{subagent_id}.json"
            state = {
                "subagent_id": subagent_id,
                "finished_naturally": result.finished_naturally,
                "turns_used": result.turns_used,
                "messages_count": len(result.messages),
            }
            with open(state_file, "w") as f:
                json.dump(state, f)
        except Exception as exc:
            logger.debug(f"Failed to save coordination state: {exc}")

    def coordinate_parallel(
        self,
        tasks: list[str],
        parent_id: str | None = None,
        depth: int = 1,
    ) -> list[Any]:
        """协调并行任务"""
        with ThreadPoolExecutor(max_workers=min(len(tasks), self.max_concurrent)) as executor:
            futures = []
            for task in tasks:
                future = executor.submit(
                    self.spawn,
                    goal=task,
                    parent_id=parent_id,
                    depth=depth,
                )
                futures.append((task, future))

            results = []
            for task, future in futures:
                try:
                    subagent_id = future.result(timeout=self.child_timeout)
                    results.append({"task": task, "subagent_id": subagent_id, "status": "spawned"})
                except FuturesTimeoutError:
                    results.append({"task": task, "status": "timeout"})
                except Exception as exc:
                    results.append({"task": task, "status": "error", "error": str(exc)})

            return results

    def pause(self) -> bool:
        """暂停子 Agent 生成"""
        return set_spawn_paused(True)

    def resume(self) -> bool:
        """恢复子 Agent 生成"""
        return set_spawn_paused(False)

    @property
    def active_count(self) -> int:
        """获取活跃子 Agent 数量"""
        with _active_subagents_lock:
            return len(_active_subagents)


_orchestrator_instance: PrometheusOrchestrator | None = None
_orchestrator_lock = threading.Lock()


def get_orchestrator() -> PrometheusOrchestrator:
    """获取全局编排者实例"""
    global _orchestrator_instance
    with _orchestrator_lock:
        if _orchestrator_instance is None:
            _orchestrator_instance = PrometheusOrchestrator()
        return _orchestrator_instance
