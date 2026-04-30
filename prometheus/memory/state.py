#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   ⚡ 普罗米修斯 · 运行时状态机 · Session State              ║
║                                                              ║
║   Prometheus 作为独立 Agent 的行为控制系统。                 ║
║   管理"此刻该做什么"——运行时状态、行为约束、资源分配。      ║
║                                                              ║
║   与 G007-dormancy 的区别：                                  ║
║     G007 = 种子的生命周期（休眠→发芽→生长→开花）            ║
║     SessionState = Prometheus 的运行时状态（空闲→思考→行动） ║
║     两者独立，互不隶属。                                     ║
║                                                              ║
║   状态定义：                                                 ║
║     idle       — 空闲，等待任务                               ║
║     thinking   — 规划中，分析需求                             ║
║     acting     — 执行中，调用工具                             ║
║     waiting    — 等待外部输入/确认                            ║
║     reflecting — 自我反思/复盘                                ║
║     error      — 错误恢复中                                  ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import datetime
import json
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum

from storage import StateStore

STATE_DIR = os.path.expanduser("~/.hermes/tools/prometheus/state")
os.makedirs(STATE_DIR, exist_ok=True)


class AgentState(Enum):
    """运行时状态"""
    IDLE = "idle"                # 空闲
    THINKING = "thinking"        # 规划中
    ACTING = "acting"            # 执行中
    WAITING = "waiting"          # 等待外部
    REFLECTING = "reflecting"    # 反思中
    ERROR = "error"              # 错误恢复


# 状态元数据
STATE_META = {
    AgentState.IDLE: {
        "label": "空闲", "emoji": "💤",
        "description": "等待任务",
        "allowed_transitions": ["thinking", "reflecting"],
        "resource_allocation": "minimal",
    },
    AgentState.THINKING: {
        "label": "思考", "emoji": "🤔",
        "description": "分析需求，制定计划",
        "allowed_transitions": ["acting", "waiting", "idle", "error"],
        "resource_allocation": "moderate",
    },
    AgentState.ACTING: {
        "label": "行动", "emoji": "⚡",
        "description": "执行任务，调用工具",
        "allowed_transitions": ["thinking", "waiting", "idle", "error", "reflecting"],
        "resource_allocation": "full",
    },
    AgentState.WAITING: {
        "label": "等待", "emoji": "⏳",
        "description": "等待外部输入或确认",
        "allowed_transitions": ["thinking", "acting", "idle", "error"],
        "resource_allocation": "minimal",
    },
    AgentState.REFLECTING: {
        "label": "反思", "emoji": "🪞",
        "description": "自我反思和复盘",
        "allowed_transitions": ["idle", "thinking"],
        "resource_allocation": "moderate",
    },
    AgentState.ERROR: {
        "label": "错误", "emoji": "❌",
        "description": "错误恢复中",
        "allowed_transitions": ["idle", "thinking", "reflecting"],
        "resource_allocation": "minimal",
    },
}


@dataclass
class StateTransition:
    """状态转换记录"""
    from_state: str
    to_state: str
    timestamp: str
    reason: str = ""
    duration_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TaskContext:
    """任务上下文"""
    task_id: str = ""
    task_type: str = ""           # task_type: seed_op, tool_call, reflection, etc.
    description: str = ""
    started_at: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════
#   运行时状态机
# ═══════════════════════════════════════════

class SessionState:
    """Prometheus 的运行时状态机。
    
    控制 Agent 在任何时刻的行为模式。
    每种状态有不同的行为约束和资源分配策略。
    """

    def __init__(self, state_file: str = None, db_path: str = None):
        """初始化状态机。

        Args:
            state_file: 兼容旧接口，自动转为 .db 路径
            db_path: SQLite 数据库路径，None 则使用默认 prometheus.db
        """
        if db_path is None and state_file is not None:
            db_path = state_file.rsplit('.', 1)[0] + '.db'
        self._store = StateStore(db_path=db_path, namespace='session')
        self.current_state = AgentState.IDLE
        self.transitions: List[StateTransition] = []
        self.task: Optional[TaskContext] = None
        self.entered_at: str = datetime.datetime.now().isoformat()
        self._on_enter_hooks: Dict[str, List[Callable]] = {}
        self._on_exit_hooks: Dict[str, List[Callable]] = {}
        self._reflection = None
        self._load_state()

    # ── 状态转换 ──

    def transition(self, to_state: str, reason: str = "", context: dict = None) -> dict:
        """执行状态转换。
        
        Args:
            to_state: 目标状态
            reason: 转换原因
            context: 附加上下文信息，传递给钩子
            
        Returns:
            {success, from, to, message}
        """
        target = None
        for s in AgentState:
            if s.value == to_state:
                target = s
                break

        if not target:
            return {"success": False, "message": f"无效状态: {to_state}"}

        current = self.current_state
        meta = STATE_META.get(current, {})
        allowed = meta.get("allowed_transitions", [])

        if to_state not in allowed:
            return {
                "success": False,
                "message": f"不允许从 {current.value} 转换到 {to_state}。允许: {allowed}",
            }

        # 计算在当前状态的停留时间
        duration_ms = 0
        if self.entered_at:
            entered = datetime.datetime.fromisoformat(self.entered_at)
            duration_ms = int((datetime.datetime.now() - entered).total_seconds() * 1000)

        # 执行退出钩子
        self._run_exit_hooks(current.value)

        # 记录转换
        transition = StateTransition(
            from_state=current.value,
            to_state=to_state,
            timestamp=datetime.datetime.now().isoformat(),
            reason=reason,
            duration_ms=duration_ms,
        )
        self.transitions.append(transition)

        # 更新状态
        self.current_state = target
        self.entered_at = datetime.datetime.now().isoformat()

        # 执行进入钩子
        hook_context = context or {}
        hook_context["from_state"] = current.value
        hook_context["to_state"] = to_state
        hook_context["reason"] = reason
        self._run_enter_hooks(to_state, hook_context)

        # 持久化
        self._save_state()

        return {
            "success": True,
            "from": transition.from_state,
            "to": to_state,
            "message": f"{STATE_META[current]['emoji']} {STATE_META[current]['label']} → {STATE_META[target]['emoji']} {STATE_META[target]['label']}",
            "duration_ms": duration_ms,
        }

    def idle(self, reason: str = "") -> dict:
        return self.transition("idle", reason)

    def think(self, reason: str = "") -> dict:
        return self.transition("thinking", reason)

    def act(self, reason: str = "") -> dict:
        return self.transition("acting", reason)

    def wait(self, reason: str = "") -> dict:
        return self.transition("waiting", reason)

    def reflect(self, reason: str = "") -> dict:
        return self.transition("reflecting", reason)

    def error(self, reason: str = "") -> dict:
        return self.transition("error", reason)

    # ── 查询 ──

    def current(self) -> dict:
        """获取当前状态。"""
        meta = STATE_META.get(self.current_state, {})
        return {
            "state": self.current_state.value,
            "label": meta.get("label", ""),
            "emoji": meta.get("emoji", ""),
            "description": meta.get("description", ""),
            "resource_allocation": meta.get("resource_allocation", ""),
            "entered_at": self.entered_at,
            "allowed_transitions": meta.get("allowed_transitions", []),
        }

    def can_transition_to(self, target: str) -> bool:
        """检查是否可以转换到目标状态。"""
        meta = STATE_META.get(self.current_state, {})
        return target in meta.get("allowed_transitions", [])

    def transition_history(self, limit: int = 20) -> List[dict]:
        """状态转换历史。"""
        return [t.to_dict() for t in self.transitions[-limit:]]

    def in_state_duration_ms(self) -> int:
        """在当前状态停留的毫秒数。"""
        if not self.entered_at:
            return 0
        entered = datetime.datetime.fromisoformat(self.entered_at)
        return int((datetime.datetime.now() - entered).total_seconds() * 1000)

    def state_summary(self) -> dict:
        """状态概览。"""
        state_counts = {}
        for t in self.transitions:
            state_counts[t.from_state] = state_counts.get(t.from_state, 0) + 1

        total_time = {}
        for t in self.transitions:
            state_time = total_time.get(t.from_state, 0)
            total_time[t.from_state] = state_time + t.duration_ms

        return {
            "current": self.current(),
            "total_transitions": len(self.transitions),
            "state_counts": state_counts,
            "time_in_states_ms": total_time,
        }

    # ── 任务管理 ──

    def start_task(self, task_id: str, task_type: str = "",
                   description: str = "", metadata: dict = None) -> dict:
        """开始新任务。"""
        if self.current_state != AgentState.IDLE:
            return {
                "success": False,
                "message": f"当前状态 {self.current_state.value} 非空闲，无法开始新任务",
            }

        self.task = TaskContext(
            task_id=task_id,
            task_type=task_type,
            description=description,
            started_at=datetime.datetime.now().isoformat(),
            metadata=metadata or {},
        )

        result = self.think(reason=f"开始任务: {task_id}")
        result["task"] = self.task.to_dict()
        return result

    def complete_task(self, success: bool = True, summary: str = "") -> dict:
        """完成当前任务。"""
        if not self.task:
            return {"success": False, "message": "没有进行中的任务"}

        task_summary = {
            "task_id": self.task.task_id,
            "success": success,
            "summary": summary,
            "completed_at": datetime.datetime.now().isoformat(),
        }

        self.task = None

        if success:
            result = self.idle(reason="任务完成")
        else:
            result = self.error(reason="任务失败")

        result["task_summary"] = task_summary
        return result

    def current_task(self) -> Optional[dict]:
        """获取当前任务。"""
        return self.task.to_dict() if self.task else None

    # ── 钩子 ──

    def on_enter(self, state: str, callback: Callable):
        """注册进入状态时的钩子。"""
        if state not in self._on_enter_hooks:
            self._on_enter_hooks[state] = []
        self._on_enter_hooks[state].append(callback)

    def on_exit(self, state: str, callback: Callable):
        """注册退出状态时的钩子。"""
        if state not in self._on_exit_hooks:
            self._on_exit_hooks[state] = []
        self._on_exit_hooks[state].append(callback)

    def _run_enter_hooks(self, state: str, context: dict = None):
        """执行进入状态的钩子。
        
        Args:
            state: 进入的状态名
            context: 附加上下文（from_state, to_state, reason 等）
        """
        for hook in self._on_enter_hooks.get(state, []):
            try:
                hook(state, context or {})
            except Exception:
                pass

    def _run_exit_hooks(self, state: str, context: dict = None):
        """执行退出状态的钩子。
        
        Args:
            state: 退出的状态名
            context: 附加上下文
        """
        for hook in self._on_exit_hooks.get(state, []):
            try:
                hook(state, context or {})
            except Exception:
                pass

    # ── 持久化 ──
    # ── 自动反思联动 ──

    def setup_auto_reflection(self, reflection_module=None):
        """配置自动反思钩子。
        
        当进入 REFLECTING 状态时，自动调用 reflection_module.reflect()。
        当进入 ERROR 状态时，记录错误观察到反思模块。
        每次状态转换时，自动调用 observe_state_change() 记录。
        
        设计原则：通过参数注入实现解耦，不自动导入。
        
        Args:
            reflection_module: SelfReflection 实例（可选）
        """
        if reflection_module:
            self._reflection = reflection_module
            self.on_enter("reflecting", self._auto_reflect)
            self.on_enter("error", self._auto_observe_error)
            # 为所有状态注册状态转换观察钩子
            for s in AgentState:
                self.on_enter(s.value, self._auto_observe_transition)

    def _auto_reflect(self, state: str, context: dict):
        """自动反思钩子——进入 REFLECTING 时触发。
        
        自动调用反思模块的 reflect() 方法，并将结果
        附加到当前任务的元数据中。
        """
        if self._reflection is None:
            return
        result = self._reflection.reflect()
        if self.task:
            self.task.metadata["reflection_result"] = result

    def _auto_observe_error(self, state: str, context: dict):
        """自动错误观察钩子——进入 ERROR 时触发。
        
        将错误信息记录到反思模块的观察收集器中。
        """
        if self._reflection is None:
            return
        reason = context.get("reason", "unknown error")
        self._reflection.observe_error("state_error", reason)
    def _auto_observe_transition(self, state: str, context: dict):
        """自动状态转换观察钩子——每次进入状态时触发。
        
        将状态转换记录到反思模块的观察收集器中。
        """
        if self._reflection is None:
            return
        from_state = context.get("from_state", "")
        to_state = context.get("to_state", state)
        reason = context.get("reason", "")
        self._reflection.observe_state_change(from_state, to_state, reason)

    def _save_state(self):
        self._store.set('current_state', self.current_state.value)
        self._store.set('entered_at', self.entered_at)
        self._store.set('transitions', [t.to_dict() for t in self.transitions[-100:]])
        self._store.set('current_task', self.task.to_dict() if self.task else None)

    def _load_state(self):
        try:
            state_val = self._store.get('current_state', 'idle')
            entered_at = self._store.get('entered_at', None)
            transitions_data = self._store.get('transitions', [])
            task_data = self._store.get('current_task', None)

            for s in AgentState:
                if s.value == state_val:
                    self.current_state = s
                    break
            if entered_at:
                self.entered_at = entered_at
            self.transitions = [
                StateTransition(**t) for t in (transitions_data or [])
            ]
            if task_data:
                self.task = TaskContext(**task_data)
        except (KeyError, TypeError):
            pass


# ═══════════════════════════════════════════
#   CLI 入口
# ═══════════════════════════════════════════

def main():
    import sys

    if len(sys.argv) < 2:
        print("""
⚡ 普罗米修斯 · 运行时状态机

用法:
  session_state.py current           查看当前状态
  session_state.py transition <状态> [--reason 原因]
    状态: idle, thinking, acting, waiting, reflecting, error
  session_state.py start-task <任务ID> [--type 类型] [--desc 描述]
  session_state.py complete [--success|--failure] [--summary 摘要]
  session_state.py history [--limit 20]
  session_state.py summary           状态概览
""")
        return

    ss = SessionState()
    action = sys.argv[1]

    if action == 'current':
        s = ss.current()
        print(f"\n{s['emoji']} 当前状态: {s['state']} ({s['label']})")
        print(f"  {s['description']}")
        print(f"  资源分配: {s['resource_allocation']}")
        print(f"  允许转换: {s['allowed_transitions']}")
        print(f"  进入时间: {s['entered_at'][:19]}")
        if ss.task:
            print(f"  当前任务: {ss.task.task_id}")

    elif action == 'transition' and len(sys.argv) > 2:
        to_state = sys.argv[2]
        reason = ""
        if '--reason' in sys.argv:
            idx = sys.argv.index('--reason')
            reason = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""

        result = ss.transition(to_state, reason)
        print(f"{'✅' if result['success'] else '❌'} {result['message']}")

    elif action == 'start-task' and len(sys.argv) > 2:
        task_id = sys.argv[2]
        task_type = ""
        desc = ""
        if '--type' in sys.argv:
            idx = sys.argv.index('--type')
            task_type = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
        if '--desc' in sys.argv:
            idx = sys.argv.index('--desc')
            desc = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""

        result = ss.start_task(task_id, task_type=task_type, description=desc)
        print(f"{'✅' if result['success'] else '❌'} {result['message']}")

    elif action == 'complete':
        success = '--failure' not in sys.argv
        summary = ""
        if '--summary' in sys.argv:
            idx = sys.argv.index('--summary')
            summary = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""

        result = ss.complete_task(success=success, summary=summary)
        print(f"{'✅' if result['success'] else '❌'} {result['message']}")

    elif action == 'history':
        limit = 20
        if '--limit' in sys.argv:
            idx = sys.argv.index('--limit')
            limit = int(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else 20

        history = ss.transition_history(limit)
        print(f"\n📋 转换历史 ({len(history)} 条):")
        for t in history:
            print(f"  {t['from_state']} → {t['to_state']} ({t['duration_ms']}ms) {t['reason']}")

    elif action == 'summary':
        s = ss.state_summary()
        print(f"\n📊 状态概览:")
        print(f"  当前: {s['current']['emoji']} {s['current']['state']} ({s['current']['label']})")
        print(f"  总转换: {s['total_transitions']} 次")
        if s['state_counts']:
            print(f"  状态分布:")
            for state, count in sorted(s['state_counts'].items(), key=lambda x: -x[1]):
                print(f"    {state}: {count}")

    else:
        print(f"未知命令: {action}")


if __name__ == "__main__":
    main()
