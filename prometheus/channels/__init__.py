"""Prometheus 消息频道模块."""

from .base import (
    CHANNEL_TYPE_MAP,
    Channel,
    ChannelConfig,
    ChannelMessage,
    ChannelResponse,
    ChannelType,
    CLIChannel,
    FileWatchChannel,
    HTTPWebhookChannel,
    MQTTChannel,
    WebSocketChannel,
)
from .manager import (
    PLATFORMS,
    ChannelManager,
    PlatformInfo,
    PlatformType,
    get_channel_manager,
)
from .registry import (
    ChannelRegistry,
    create_default_channels,
    get_channel_registry,
    register_channel_type,
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
