"""
频道基类定义

参照 OpenClaw gateway channel 抽象与 Hermes message handler 模式，
定义频道的统一数据模型与接口。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, Callable, List
from abc import ABC, abstractmethod


class ChannelType(Enum):
    CLI = "cli"
    HTTP_WEBHOOK = "http_webhook"
    FILE_WATCH = "file_watch"
    WEB_SOCKET = "web_socket"
    MQTT = "mqtt"


@dataclass
class ChannelConfig:
    channel_type: ChannelType
    name: str
    enabled: bool = True
    settings: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "channel_type": self.channel_type.value,
            "name": self.name,
            "enabled": self.enabled,
            "settings": self.settings,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChannelConfig":
        channel_type = data.get("channel_type", "cli")
        if isinstance(channel_type, str):
            channel_type = ChannelType(channel_type)
        return cls(
            channel_type=channel_type,
            name=data.get("name", ""),
            enabled=data.get("enabled", True),
            settings=data.get("settings", {}),
        )


@dataclass
class ChannelMessage:
    channel: str
    sender: str = "unknown"
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    reply_to: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "channel": self.channel,
            "sender": self.sender,
            "content": self.content,
            "metadata": self.metadata,
            "reply_to": self.reply_to,
        }


@dataclass
class ChannelResponse:
    content: str
    channel: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "channel": self.channel,
            "metadata": self.metadata,
            "error": self.error,
        }


class Channel(ABC):
    def __init__(self, config: ChannelConfig):
        self.config = config
        self._started = False
        self._on_message: Optional[Callable[[ChannelMessage], Optional[ChannelResponse]]] = None

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def channel_type(self) -> ChannelType:
        return self.config.channel_type

    @property
    def is_started(self) -> bool:
        return self._started

    def set_handler(self, handler: Callable[[ChannelMessage], Optional[ChannelResponse]]):
        self._on_message = handler

    def handle_message(self, message: ChannelMessage) -> Optional[ChannelResponse]:
        if self._on_message:
            return self._on_message(message)
        return None

    @abstractmethod
    def start(self) -> bool:
        pass

    @abstractmethod
    def stop(self) -> bool:
        pass

    @abstractmethod
    def send(self, response: ChannelResponse) -> bool:
        pass

    def status(self) -> dict:
        return {
            "name": self.name,
            "type": self.channel_type.value,
            "enabled": self.config.enabled,
            "started": self._started,
        }


class CLIChannel(Channel):
    def start(self) -> bool:
        self._started = True
        return True

    def stop(self) -> bool:
        self._started = False
        return True

    def send(self, response: ChannelResponse) -> bool:
        print(response.content)
        if response.error:
            print(f"[错误] {response.error}")
        return True

    def receive(self, sender: str = "cli", content: str = "", metadata: dict = None) -> Optional[ChannelResponse]:
        if not self._started:
            return None
        message = ChannelMessage(
            channel=self.name,
            sender=sender,
            content=content,
            metadata=metadata or {},
        )
        return self.handle_message(message)


class HTTPWebhookChannel(Channel):
    def start(self) -> bool:
        self._started = True
        return True

    def stop(self) -> bool:
        self._started = False
        return True

    def send(self, response: ChannelResponse) -> bool:
        return True

    def receive_request(self, sender: str, content: str, metadata: dict = None) -> Optional[ChannelResponse]:
        if not self._started:
            return None
        message = ChannelMessage(
            channel=self.name,
            sender=sender,
            content=content,
            metadata=metadata or {},
        )
        return self.handle_message(message)


class FileWatchChannel(Channel):
    def start(self) -> bool:
        self._started = True
        return True

    def stop(self) -> bool:
        self._started = False
        return True

    def send(self, response: ChannelResponse) -> bool:
        return True

    def on_file_change(self, filepath: str, action: str = "modified") -> Optional[ChannelResponse]:
        if not self._started:
            return None
        message = ChannelMessage(
            channel=self.name,
            sender=f"file_watcher:{filepath}",
            content=f"文件{action}: {filepath}",
            metadata={"filepath": filepath, "action": action},
        )
        return self.handle_message(message)


CHANNEL_TYPE_MAP: Dict[ChannelType, type] = {
    ChannelType.CLI: CLIChannel,
    ChannelType.HTTP_WEBHOOK: HTTPWebhookChannel,
    ChannelType.FILE_WATCH: FileWatchChannel,
}
