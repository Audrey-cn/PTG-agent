"""
频道注册中心

管理所有活跃的消息频道，提供统一的频道生命周期管理。
参照 OpenClaw gateway 的 channel manager 模式。
"""

from typing import Dict, List, Optional, Callable

from .base import (
    Channel,
    ChannelType,
    ChannelConfig,
    ChannelMessage,
    ChannelResponse,
    CLIChannel,
    HTTPWebhookChannel,
    FileWatchChannel,
    CHANNEL_TYPE_MAP,
)


class ChannelRegistry:
    def __init__(self):
        self._channels: Dict[str, Channel] = {}
        self._global_handler: Optional[Callable[[ChannelMessage], Optional[ChannelResponse]]] = None

    def set_global_handler(self, handler: Callable[[ChannelMessage], Optional[ChannelResponse]]):
        self._global_handler = handler
        for channel in self._channels.values():
            channel.set_handler(handler)

    def register(self, channel: Channel) -> bool:
        if channel.name in self._channels:
            return False
        if self._global_handler:
            channel.set_handler(self._global_handler)
        self._channels[channel.name] = channel
        return True

    def unregister(self, name: str) -> bool:
        if name not in self._channels:
            return False
        if self._channels[name].is_started:
            self._channels[name].stop()
        del self._channels[name]
        return True

    def get(self, name: str) -> Optional[Channel]:
        return self._channels.get(name)

    def create_channel(self, config: ChannelConfig) -> Optional[Channel]:
        channel_cls = CHANNEL_TYPE_MAP.get(config.channel_type)
        if channel_cls is None:
            return None
        channel = channel_cls(config)
        if self._global_handler:
            channel.set_handler(self._global_handler)
        self._channels[config.name] = channel
        return channel

    def start_all(self) -> Dict[str, bool]:
        results = {}
        for name, channel in self._channels.items():
            if channel.config.enabled:
                results[name] = channel.start()
            else:
                results[name] = False
        return results

    def stop_all(self) -> Dict[str, bool]:
        results = {}
        for name, channel in self._channels.items():
            results[name] = channel.stop()
        return results

    def start(self, name: str) -> bool:
        channel = self._channels.get(name)
        if channel and channel.config.enabled:
            return channel.start()
        return False

    def stop(self, name: str) -> bool:
        channel = self._channels.get(name)
        if channel:
            return channel.stop()
        return False

    def list_all(self) -> List[dict]:
        return [c.status() for c in self._channels.values()]

    def broadcast(self, response: ChannelResponse) -> Dict[str, bool]:
        results = {}
        for name, channel in self._channels.items():
            if channel.is_started:
                results[name] = channel.send(response)
            else:
                results[name] = False
        return results

    @property
    def channels(self) -> Dict[str, Channel]:
        return dict(self._channels)

    @property
    def active_count(self) -> int:
        return sum(1 for c in self._channels.values() if c.is_started)

    @property
    def total_count(self) -> int:
        return len(self._channels)


_registry: Optional[ChannelRegistry] = None


def get_channel_registry() -> ChannelRegistry:
    global _registry
    if _registry is None:
        _registry = ChannelRegistry()
    return _registry


def register_channel_type(channel_type: ChannelType, channel_cls: type):
    CHANNEL_TYPE_MAP[channel_type] = channel_cls


def create_default_channels(workspace_dir: str = None) -> ChannelRegistry:
    """创建默认频道集: CLI (始终启用)"""
    registry = get_channel_registry()

    cli_config = ChannelConfig(
        channel_type=ChannelType.CLI,
        name="cli",
        enabled=True,
    )
    registry.create_channel(cli_config)

    return registry
