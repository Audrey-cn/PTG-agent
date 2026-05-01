#!/usr/bin/env python3
"""Prometheus 任务/工作流引擎."""

import asyncio
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Union

from prometheus._paths import get_paths

logger = logging.getLogger("prometheus.taskflow")


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TaskPriority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class WorkflowNodeType(Enum):
    TASK = "task"
    PARALLEL = "parallel"
    SEQUENCE = "sequence"
    CONDITIONAL = "conditional"
    LOOP = "loop"


@dataclass
class TaskDefinition:
    """任务定义"""

    task_id: str
    name: str
    description: str = ""
    type: str = "python"
    handler: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    priority: str = TaskPriority.NORMAL.value
    timeout: int = 300
    retries: int = 0
    retry_delay: int = 5
    dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskInstance:
    """任务实例"""

    instance_id: str
    task_id: str
    status: str = TaskStatus.PENDING.value
    created_at: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    result: Any | None = None
    error: str | None = None
    retry_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class WorkflowNode:
    """工作流节点"""

    node_id: str
    type: str
    tasks: list[Union[str, "WorkflowNode"]] = field(default_factory=list)
    condition: str | None = None
    loop_count: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowDefinition:
    """工作流定义"""

    workflow_id: str
    name: str
    description: str = ""
    root: WorkflowNode = None
    tasks: dict[str, TaskDefinition] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowInstance:
    """工作流实例"""

    instance_id: str
    workflow_id: str
    status: str = TaskStatus.PENDING.value
    created_at: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    result: Any | None = None
    error: str | None = None
    task_results: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class TaskExecutor:
    """任务执行器"""

    def __init__(self):
        self._handlers: dict[str, Callable] = {}

    def register_handler(self, task_type: str, handler: Callable):
        """注册任务处理器"""
        self._handlers[task_type] = handler

    def get_handler(self, task_type: str) -> Callable | None:
        """获取任务处理器"""
        return self._handlers.get(task_type)

    async def execute_task(self, task: TaskDefinition) -> Any:
        """执行任务"""
        handler = self.get_handler(task.type)

        if not handler:
            raise ValueError(f"No handler registered for task type: {task.type}")

        try:
            if asyncio.iscoroutinefunction(handler):
                return await handler(task)
            else:
                return handler(task)
        except Exception as e:
            raise RuntimeError(f"Task execution failed: {e}")


class TaskFlowEngine:
    """任务工作流引擎"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tasks: dict[str, TaskDefinition] = {}
            cls._task_instances: dict[str, TaskInstance] = {}
            cls._workflows: dict[str, WorkflowDefinition] = {}
            cls._workflow_instances: dict[str, WorkflowInstance] = {}
            cls._executor = TaskExecutor()
            cls._data_dir = get_paths().tasks
            cls._data_dir.mkdir(parents=True, exist_ok=True)
        return cls._instance

    def register_task(self, task: TaskDefinition):
        """注册任务定义"""
        self._tasks[task.task_id] = task
        logger.info(f"Registered task: {task.name} ({task.task_id})")

    def get_task(self, task_id: str) -> TaskDefinition | None:
        """获取任务定义"""
        return self._tasks.get(task_id)

    def register_workflow(self, workflow: WorkflowDefinition):
        """注册工作流定义"""
        self._workflows[workflow.workflow_id] = workflow
        logger.info(f"Registered workflow: {workflow.name} ({workflow.workflow_id})")

    def get_workflow(self, workflow_id: str) -> WorkflowDefinition | None:
        """获取工作流定义"""
        return self._workflows.get(workflow_id)

    def register_handler(self, task_type: str, handler: Callable):
        """注册任务处理器"""
        self._executor.register_handler(task_type, handler)

    async def run_task(self, task_id: str, **kwargs) -> TaskInstance:
        """运行单个任务"""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        instance = TaskInstance(
            instance_id=str(uuid.uuid4())[:8],
            task_id=task_id,
            metadata=kwargs.get("metadata", {}),
        )
        self._task_instances[instance.instance_id] = instance

        return await self._execute_task_instance(instance, task, kwargs.get("args", {}))

    async def _execute_task_instance(
        self, instance: TaskInstance, task: TaskDefinition, extra_args: dict[str, Any] = None
    ) -> TaskInstance:
        """执行任务实例"""

        for attempt in range(task.retries + 1):
            instance.status = TaskStatus.RUNNING.value
            instance.started_at = datetime.now().isoformat()

            try:
                result = await self._executor.execute_task(task)

                instance.status = TaskStatus.COMPLETED.value
                instance.result = result
                instance.completed_at = datetime.now().isoformat()
                return instance

            except Exception as e:
                instance.error = str(e)
                instance.retry_count += 1

                if attempt < task.retries:
                    logger.warning(
                        f"Task {task.task_id} failed (attempt {attempt + 1}/{task.retries + 1}): {e}"
                    )
                    await asyncio.sleep(task.retry_delay * (2**attempt))
                else:
                    instance.status = TaskStatus.FAILED.value
                    instance.completed_at = datetime.now().isoformat()
                    logger.error(
                        f"Task {task.task_id} failed after {task.retries + 1} attempts: {e}"
                    )
                    return instance

    async def run_workflow(self, workflow_id: str, **kwargs) -> WorkflowInstance:
        """运行工作流"""
        workflow = self.get_workflow(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")

        instance = WorkflowInstance(
            instance_id=str(uuid.uuid4())[:8],
            workflow_id=workflow_id,
            metadata=kwargs.get("metadata", {}),
        )
        self._workflow_instances[instance.instance_id] = instance

        return await self._execute_workflow_node(instance, workflow.root)

    async def _execute_workflow_node(
        self, instance: WorkflowInstance, node: WorkflowNode
    ) -> WorkflowInstance:
        """执行工作流节点"""
        instance.status = TaskStatus.RUNNING.value
        instance.started_at = datetime.now().isoformat()

        try:
            if node.type == WorkflowNodeType.TASK.value:
                task_ids = node.tasks if isinstance(node.tasks, list) else [node.tasks]
                for task_id in task_ids:
                    task = self.get_task(task_id)
                    if task:
                        task_instance = await self.run_task(task_id)
                        instance.task_results[task_id] = task_instance.result

            elif node.type == WorkflowNodeType.SEQUENCE.value:
                for child in node.tasks:
                    if isinstance(child, WorkflowNode):
                        await self._execute_workflow_node(instance, child)
                    else:
                        task = self.get_task(child)
                        if task:
                            task_instance = await self.run_task(child)
                            instance.task_results[child] = task_instance.result

            elif node.type == WorkflowNodeType.PARALLEL.value:
                tasks = []
                for child in node.tasks:
                    if isinstance(child, WorkflowNode):
                        tasks.append(self._execute_workflow_node(instance, child))
                    else:
                        tasks.append(self.run_task(child))

                results = await asyncio.gather(*tasks)
                for i, child in enumerate(node.tasks):
                    if isinstance(child, str):
                        instance.task_results[child] = (
                            results[i].result if hasattr(results[i], "result") else results[i]
                        )

            elif node.type == WorkflowNodeType.CONDITIONAL.value:
                condition_result = self._evaluate_condition(node.condition, instance.task_results)
                if condition_result:
                    for child in node.tasks:
                        if isinstance(child, WorkflowNode):
                            await self._execute_workflow_node(instance, child)
                        else:
                            task_instance = await self.run_task(child)
                            instance.task_results[child] = task_instance.result

            elif node.type == WorkflowNodeType.LOOP.value:
                for _ in range(node.loop_count):
                    for child in node.tasks:
                        if isinstance(child, WorkflowNode):
                            await self._execute_workflow_node(instance, child)
                        else:
                            task_instance = await self.run_task(child)
                            instance.task_results[child] = task_instance.result

            instance.status = TaskStatus.COMPLETED.value
            instance.completed_at = datetime.now().isoformat()
            instance.result = instance.task_results

        except Exception as e:
            instance.status = TaskStatus.FAILED.value
            instance.error = str(e)
            instance.completed_at = datetime.now().isoformat()
            logger.error(f"Workflow {instance.workflow_id} failed: {e}")

        return instance

    def _evaluate_condition(self, condition: str, results: dict[str, Any]) -> bool:
        """评估条件表达式"""
        try:
            local_vars = {k: v for k, v in results.items()}
            return bool(eval(condition, {}, local_vars))
        except Exception as e:
            logger.error(f"Failed to evaluate condition: {e}")
            return False

    def create_task(self, name: str, **kwargs) -> TaskDefinition:
        """便捷方法：创建任务"""
        task_id = kwargs.get("task_id", str(uuid.uuid4())[:8])
        return TaskDefinition(task_id=task_id, name=name, **kwargs)

    def create_workflow(self, name: str, root: WorkflowNode, **kwargs) -> WorkflowDefinition:
        """便捷方法：创建工作流"""
        workflow_id = kwargs.get("workflow_id", str(uuid.uuid4())[:8])
        return WorkflowDefinition(workflow_id=workflow_id, name=name, root=root, **kwargs)

    def list_tasks(self) -> list[TaskDefinition]:
        """列出所有任务"""
        return list(self._tasks.values())

    def list_workflows(self) -> list[WorkflowDefinition]:
        """列出所有工作流"""
        return list(self._workflows.values())

    def get_task_instance(self, instance_id: str) -> TaskInstance | None:
        """获取任务实例"""
        return self._task_instances.get(instance_id)

    def get_workflow_instance(self, instance_id: str) -> WorkflowInstance | None:
        """获取工作流实例"""
        return self._workflow_instances.get(instance_id)

    def cancel_task(self, instance_id: str):
        """取消任务"""
        if instance_id in self._task_instances:
            instance = self._task_instances[instance_id]
            instance.status = TaskStatus.CANCELLED.value
            instance.completed_at = datetime.now().isoformat()
            logger.info(f"Cancelled task instance: {instance_id}")

    def cancel_workflow(self, instance_id: str):
        """取消工作流"""
        if instance_id in self._workflow_instances:
            instance = self._workflow_instances[instance_id]
            instance.status = TaskStatus.CANCELLED.value
            instance.completed_at = datetime.now().isoformat()
            logger.info(f"Cancelled workflow instance: {instance_id}")


def get_task_flow_engine() -> TaskFlowEngine:
    """获取全局任务流引擎"""
    return TaskFlowEngine()


def register_builtin_handlers():
    """注册内置任务处理器"""
    engine = get_task_flow_engine()

    async def python_task_handler(task: TaskDefinition):
        """Python 代码执行处理器"""
        code = task.args.get("code", "")
        if not code:
            raise ValueError("No code provided for python task")

        local_vars = {}
        exec(code, {}, local_vars)

        if "result" in local_vars:
            return local_vars["result"]
        return None

    async def delay_handler(task: TaskDefinition):
        """延迟任务处理器"""
        delay = task.args.get("delay", 1)
        await asyncio.sleep(delay)
        return {"delayed": delay}

    async def http_request_handler(task: TaskDefinition):
        """HTTP 请求处理器"""
        import aiohttp

        url = task.args.get("url")
        method = task.args.get("method", "GET")
        headers = task.args.get("headers", {})
        data = task.args.get("data")

        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, headers=headers, json=data) as response:
                return await response.json()

    engine.register_handler("python", python_task_handler)
    engine.register_handler("delay", delay_handler)
    engine.register_handler("http", http_request_handler)
