"""
Prometheus 消息频道模块

提供统一的频道接口，支持多种交互方式：
- CLI: 默认命令行
- HTTP Webhook: API 接口
- File Watch: 文件监听
- WebSocket (placeholder): WebSocket
- MQTT (placeholder): MQTT
- Telegram/Discord/Slack/飞书/钉钉 等第三方平台
"""

from .base import (
    Channel,
    ChannelType,
    ChannelConfig,
    ChannelMessage,
    ChannelResponse,
    CLIChannel,
    HTTPWebhookChannel,
    FileWatchChannel,
    WebSocketChannel,
    MQTTChannel,
    CHANNEL_TYPE_MAP,
)

from .registry import (
    ChannelRegistry,
    get_channel_registry,
    register_channel_type,
    create_default_channels,
)

from .manager import (
    ChannelManager,
    get_channel_manager,
    PlatformType,
    PlatformInfo,
    PLATFORMS,
)

__all__ = [
    # Base
    "Channel",
    "ChannelType",
    "ChannelConfig",
    "ChannelMessage",
    "ChannelResponse",
    # Implementations
    "CLIChannel",
    "HTTPWebhookChannel",
    "FileWatchChannel",
    "WebSocketChannel",
    "MQTTChannel",
    "CHANNEL_TYPE_MAP",
    # Registry
    "ChannelRegistry",
    "get_channel_registry",
    "register_channel_type",
    "create_default_channels",
    # Manager
    "ChannelManager",
    "get_channel_manager",
    "PlatformType",
    "PlatformInfo",
    "PLATFORMS",
]
