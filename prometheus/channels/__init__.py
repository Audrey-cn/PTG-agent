"""
消息频道抽象层

参照 OpenClaw gateway channels 与 Hermes (ElizaOS) AgentRuntime 的消息处理模式，
提供统一的消息频道注册、路由、接收与响应机制。

频道类型:
- CLI: 默认命令行交互频道（始终启用）
- HTTP_Webhook: HTTP API 接口频道
- File_Watch: 文件监听频道（监控目录变化触发任务）
"""

from .base import (
    Channel,
    ChannelType,
    ChannelConfig,
    ChannelMessage,
    ChannelResponse,
)

from .registry import (
    ChannelRegistry,
    get_channel_registry,
    register_channel_type,
)

__all__ = [
    "Channel",
    "ChannelType",
    "ChannelConfig",
    "ChannelMessage",
    "ChannelResponse",
    "ChannelRegistry",
    "get_channel_registry",
    "register_channel_type",
]
