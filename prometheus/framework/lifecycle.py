"""🔥 普罗米修斯生命周期 — PrometheusLifecycle."""

from __future__ import annotations

import contextlib
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from prometheus.chronicler import Chronicler
from prometheus.framework.firekeeper import FireKeeper
from prometheus.framework.soul_orchestrator import SoulOrchestrator
from prometheus.semantic_audit import SemanticAuditEngine


@dataclass
class SessionInfo:
    """会话信息"""

    session_id: str
    cwd: str
    mode: str = "prometheus"
    seed_path: str | None = None
    started_at: datetime = field(default_factory=datetime.now)
    tool_calls: int = 0
    messages: int = 0
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCallEvent:
    """工具调用事件"""

    tool_name: str
    args: dict[str, Any]
    result: Any
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SessionEndReport:
    """会话结束报告"""

    seed_path: str | None = None
    tool_calls: int = 0
    duration_seconds: float = 0.0
    evolution_hints: list[str] = field(default_factory=list)
    archive_path: str | None = None


class PrometheusLifecycle:
    """普罗米修斯生命周期管理器"""

    def __init__(self):
        self.chronicler = Chronicler()
        self.firekeeper = FireKeeper()
        self.soul = SoulOrchestrator()
        self.engine = SemanticAuditEngine()

        self._session: SessionInfo | None = None
        self._tool_events: list[ToolCallEvent] = []
        self._messages: list[dict[str, Any]] = []

    def on_session_start(self, cwd: str, session_id: str) -> dict[str, Any]:
        """
        会话开始 - 普罗米修斯苏醒

        1. 识别环境中是否有火种
        2. 如果有，激活普罗米修斯模式
        3. 预热种子
        """
        # 创建会话信息
        self._session = SessionInfo(session_id=session_id, cwd=cwd)

        # 检测种子
        seed = self.firekeeper.detect_seed_in_cwd(cwd)
        self._session.seed_path = seed

        if seed:
            # 有种子，激活普罗米修斯模式
            self.firekeeper.warm_seed(seed)
            self._session.mode = "prometheus"
            return {"mode": "prometheus", "seed": seed, "context": {"prometheus_awake": True}}

        # 没有种子，保持 Prometheus 模式
        return {"mode": "prometheus", "seed": None, "context": {}}

    def on_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """每条消息 - 普罗米修斯倾听并思考"""
        self._messages.append(message)

        if self._session:
            self._session.messages += 1

        # 如果有种子，注入普罗米修斯语境
        if self._session and self._session.mode == "prometheus":
            return {"context": {"prometheus_awake": True, "seed_path": self._session.seed_path}}

        return {}

    def on_tool_call(self, tool_name: str, args: dict[str, Any], result: Any) -> dict[str, Any]:
        """工具调用后 - 普罗米修斯铭刻"""
        event = ToolCallEvent(tool_name=tool_name, args=args, result=result)
        self._tool_events.append(event)

        if self._session:
            self._session.tool_calls += 1

        # 识别重要工具调用
        if tool_name in ["file_write", "edit", "skills_install", "skill_install"]:
            # 有种子时进行铭刻
            if self._session and self._session.seed_path:
                try:
                    narrative = self._generate_narrative(tool_name, args)
                    self.chronicler.append(
                        seed_path=self._session.seed_path, narrative=narrative, author="Prometheus"
                    )
                except Exception:
                    pass

        return {"recorded": True}

    def _generate_narrative(self, tool_name: str, args: dict[str, Any]) -> str:
        """生成史诗叙事"""
        if tool_name in ["file_write", "edit"]:
            path = args.get("path", "unknown")
            return f"普罗米修斯通过 {tool_name} 赋能种子: {path}"
        elif tool_name in ["skills_install", "skill_install"]:
            name = args.get("name", "unknown")
            return f"普罗米修斯为火种注入新技能: {name}"
        else:
            return f"普罗米修斯使用工具: {tool_name}"

    def on_session_end(self, messages: list[Any], final_state: Any) -> SessionEndReport:
        """会话结束 - 普罗米修斯检视与归档"""
        report = SessionEndReport()

        if self._session:
            report.seed_path = self._session.seed_path
            report.tool_calls = self._session.tool_calls

            # 计算持续时间
            duration = (datetime.now() - self._session.started_at).total_seconds()
            report.duration_seconds = duration

            # 如果有种子，生成进化提示
            if self._session.seed_path:
                report.evolution_hints = self._generate_evolution_hints()

                # 尝试归档
                with contextlib.suppress(Exception):
                    report.archive_path = self._archive_session(messages)

        return report

    def _generate_evolution_hints(self) -> list[str]:
        """生成进化提示"""
        hints = []

        # 简单规则
        if self._session and self._session.tool_calls > 5:
            hints.append("工具调用频繁，可考虑创建技能")

        if self._messages and len(self._messages) > 10:
            hints.append("会话较长，可考虑压缩或归档")

        return hints

    def _archive_session(self, messages: list[Any]) -> str | None:
        """归档会话（简单实现）"""
        if not self._session:
            return None

        # 简单的归档到记忆系统目录
        try:
            memories_dir = os.path.join(os.path.expanduser("~/.prometheus"), "memories")
            os.makedirs(memories_dir, exist_ok=True)
            session_name = f"session_{self._session.session_id}.md"
            archive_path = os.path.join(memories_dir, session_name)

            with open(archive_path, "w", encoding="utf-8") as f:
                f.write(f"# Session Archive - {self._session.session_id}\n\n")
                f.write(f"- Started: {self._session.started_at}\n")
                f.write(f"- Messages: {self._session.messages}\n")
                f.write(f"- Tool calls: {self._session.tool_calls}\n")

            return archive_path
        except Exception:
            return None

    @property
    def current_session(self) -> SessionInfo | None:
        return self._session
