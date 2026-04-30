"""
Agent 管理系统

参照 Hermes (ElizaOS) AgentRuntime 的 agent 生命周期管理,
提供多 Agent 的创建、启动、停止、监控能力。

每个 Agent 拥有:
- 独立的模型配置
- 独立的工具集
- 独立的频道绑定
- 独立的状态机
"""

from .manager import (
    AgentConfig,
    AgentInstance,
    AgentManager,
    get_agent_manager,
    create_default_agent,
)

__all__ = [
    "AgentConfig",
    "AgentInstance",
    "AgentManager",
    "get_agent_manager",
    "create_default_agent",
]
