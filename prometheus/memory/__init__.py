#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   🧠 普罗米修斯 · 记忆系统 · Memory System                  ║
║                                                              ║
║   混合存储架构：                                              ║
║     - MD 文件：人可读、编辑器友好、Git 友好                  ║
║     - SQLite：高效查询、向量检索、全文搜索                   ║
║     - 自动备份：每日/每小时备份，可手动恢复                  ║
║                                                              ║
║   三层记忆模型：                                              ║
║     工作记忆（working）  — 当前任务上下文                    ║
║     情景记忆（episodic） — 近期交互，随时间衰减              ║
║     长期记忆（longterm） — 稳定事实，持久保存                ║
╚══════════════════════════════════════════════════════════════╝
"""

from .storage import HybridStorage, MemoryRecord
from .sync import SyncManager
from .backup import BackupManager
from .context import ContextManager, MemoryLayer, MemoryUnit, estimate_tokens
from .knowledge import CompiledKnowledgeManager
from .semantic import SemanticStore
from .state import AgentState, StateTransition, TaskContext, SessionState

__all__ = [
    "HybridStorage",
    "MemoryRecord",
    "SyncManager",
    "BackupManager",
    "ContextManager",
    "MemoryLayer",
    "MemoryUnit",
    "estimate_tokens",
    "CompiledKnowledgeManager",
    "SemanticStore",
    "AgentState",
    "StateTransition",
    "TaskContext",
    "SessionState",
]
