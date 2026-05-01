"""频道基类定义."""

import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

# Optional dependencies - check availability
WATCHDOG_AVAILABLE = False
try:
    from watchdog.events import FileModifiedEvent, FileSystemEventHandler
    from watchdog.observers import Observer

    WATCHDOG_AVAILABLE = True
except ImportError:
    pass

FASTAPI_AVAILABLE = False
try:
    import fastapi
    import uvicorn
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel

    FASTAPI_AVAILABLE = True
except ImportError:
    pass


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
    settings: dict[str, Any] = field(default_factory=dict)

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
    metadata: dict[str, Any] = field(default_factory=dict)
    reply_to: str | None = None

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
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

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
        self._on_message: Callable[[ChannelMessage], ChannelResponse | None] | None = None
        self._message_history: deque = deque(maxlen=100)  # 最近 100 条消息

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def channel_type(self) -> ChannelType:
        return self.config.channel_type

    @property
    def is_started(self) -> bool:
        return self._started

    def set_handler(self, handler: Callable[[ChannelMessage], ChannelResponse | None]):
        self._on_message = handler

    def handle_message(self, message: ChannelMessage) -> ChannelResponse | None:
        self._message_history.append(message)
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

    def get_message_history(self) -> list[ChannelMessage]:
        return list(self._message_history)

    def status(self) -> dict:
        return {
            "name": self.name,
            "type": self.channel_type.value,
            "enabled": self.config.enabled,
            "started": self._started,
            "messages_count": len(self._message_history),
        }


class CLIChannel(Channel):
    """
    CLI 交互频道（默认启用）
    不需要额外依赖
    """

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self._history_size = config.settings.get("history_size", 100)

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

    def receive(
        self, sender: str = "cli", content: str = "", metadata: dict = None
    ) -> ChannelResponse | None:
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
    """
    HTTP Webhook 频道（需要 fastapi/uvicorn）
    启动一个本地 API 服务器
    """

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self._host = config.settings.get("host", "0.0.0.0")
        self._port = int(config.settings.get("port", 9090))
        self._webhook_path = config.settings.get("webhook_path", "/webhook")
        self._server_thread = None
        self._app = None
        self._uvicorn_config = None

    def start(self) -> bool:
        if not FASTAPI_AVAILABLE:
            print('⚠️ HTTP Webhook 需要 fastapi/uvicorn，请安装: pip install "prometheus-ptg[web]"')
            return False

        try:
            self._app = FastAPI(title="Prometheus Webhook Channel")

            # 定义请求模型
            class WebhookPayload(BaseModel):
                sender: str = "webhook"
                content: str = ""
                metadata: dict[str, Any] = field(default_factory=dict)

            # 定义路由
            @self._app.get("/")
            async def root():
                return {"status": "ok", "channel": self.name, "path": self._webhook_path}

            @self._app.post(self._webhook_path)
            async def receive_webhook(payload: WebhookPayload):
                if not self._started:
                    raise HTTPException(status_code=503, detail="Channel not started")

                message = ChannelMessage(
                    channel=self.name,
                    sender=payload.sender,
                    content=payload.content,
                    metadata=payload.metadata or {},
                )

                response = self.handle_message(message)
                if response:
                    return response.to_dict()
                else:
                    return {"status": "accepted"}

            # 在后台线程运行服务器
            def run_server():
                uvicorn.run(self._app, host=self._host, port=self._port, log_level="warning")

            self._server_thread = threading.Thread(target=run_server, daemon=True)
            self._server_thread.start()
            self._started = True
            return True

        except Exception as e:
            print(f"⚠️ HTTP Webhook 启动失败: {e}")
            return False

    def stop(self) -> bool:
        self._started = False
        # 注意：uvicorn 在 daemon 线程会随程序退出自动结束
        return True

    def send(self, response: ChannelResponse) -> bool:
        # HTTP Webhook send: 可以在这里实现回调通知
        # 暂时只打印
        print(f"[webhook] 发送响应: {response.content[:50] if response.content else ''}")
        return True

    def receive_request(
        self, sender: str, content: str, metadata: dict = None
    ) -> ChannelResponse | None:
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
    """
    文件监听频道（需要 watchdog）
    监听文件/目录变化
    """

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self._watch_dir = Path(config.settings.get("watch_dir", "~/.prometheus/inbox")).expanduser()
        self._pattern = config.settings.get("pattern", "*")
        self._observer = None
        self._event_handler = None

    def start(self) -> bool:
        if not WATCHDOG_AVAILABLE:
            print("⚠️ File Watch 需要 watchdog，请安装: pip install watchdog")
            return False

        try:
            self._watch_dir.mkdir(parents=True, exist_ok=True)

            class WatchHandler(FileSystemEventHandler):
                def __init__(self, channel: FileWatchChannel):
                    self._channel = channel

                def on_modified(self, event):
                    if event.is_directory:
                        return
                    if self._pattern and self._pattern != "*":
                        if not event.src_path.endswith(self._pattern.replace("*", "")):
                            return

                    self._channel.on_file_change(event.src_path, "modified")

                def on_created(self, event):
                    if event.is_directory:
                        return
                    self._channel.on_file_change(event.src_path, "created")

            self._event_handler = WatchHandler(self)
            self._observer = Observer()
            self._observer.schedule(self._event_handler, str(self._watch_dir), recursive=True)
            self._observer.start()
            self._started = True
            return True

        except Exception as e:
            print(f"⚠️ File Watch 启动失败: {e}")
            return False

    def stop(self) -> bool:
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=2)
        self._started = False
        return True

    def send(self, response: ChannelResponse) -> bool:
        # 保存到响应文件
        try:
            out_path = self._watch_dir / "responses"
            out_path.mkdir(exist_ok=True)
            out_file = out_path / f"response_{int(time.time())}.md"
            out_file.write_text(response.content, encoding="utf-8")
            return True
        except Exception as e:
            print(f"⚠️ 保存响应失败: {e}")
            return False

    def on_file_change(self, filepath: str, action: str = "modified") -> ChannelResponse | None:
        if not self._started:
            return None

        try:
            path = Path(filepath)
            if path.is_file() and not path.name.startswith("."):
                # 读取文件内容
                content = path.read_text(encoding="utf-8", errors="replace")
                message = ChannelMessage(
                    channel=self.name,
                    sender=f"file_watcher:{path.name}",
                    content=content,
                    metadata={"filepath": filepath, "action": action},
                )
                return self.handle_message(message)
        except Exception as e:
            print(f"⚠️ 处理文件变化失败: {e}")

        return None


# Placeholder for WebSocket and MQTT (to be implemented later)
class WebSocketChannel(Channel):
    """WebSocket 频道（placeholder）"""

    def start(self) -> bool:
        print("⚠️ WebSocket 频道尚未完全实现")
        return False

    def stop(self) -> bool:
        self._started = False
        return True

    def send(self, response: ChannelResponse) -> bool:
        return False


class MQTTChannel(Channel):
    """MQTT 订阅频道（placeholder）"""

    def start(self) -> bool:
        print("⚠️ MQTT 频道尚未完全实现")
        return False

    def stop(self) -> bool:
        self._started = False
        return True

    def send(self, response: ChannelResponse) -> bool:
        return False


# 频道类型映射
CHANNEL_TYPE_MAP: dict[ChannelType, type] = {
    ChannelType.CLI: CLIChannel,
    ChannelType.HTTP_WEBHOOK: HTTPWebhookChannel,
    ChannelType.FILE_WATCH: FileWatchChannel,
    ChannelType.WEB_SOCKET: WebSocketChannel,
    ChannelType.MQTT: MQTTChannel,
}
