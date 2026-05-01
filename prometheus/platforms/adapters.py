"""💬 平台消息适配器 - Platform Adapters."""

from __future__ import annotations

import json
import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """通用消息格式"""

    platform: str
    content: str
    sender_id: str
    sender_name: str | None = None
    channel_id: str | None = None
    timestamp: str | None = None
    raw: dict[str, Any] | None = None
    attachments: list[Any] = field(default_factory=list)


@dataclass
class PlatformConfig:
    """平台配置"""

    enabled: bool = False
    api_key: str | None = None
    api_secret: str | None = None
    webhook_url: str | None = None
    bot_token: str | None = None


class PlatformAdapter(ABC):
    """平台适配器基类"""

    def __init__(self, config: PlatformConfig):
        self.config = config
        self._handlers: list[callable] = []

    @abstractmethod
    def send_message(self, channel_id: str, content: str) -> dict[str, Any]:
        """发送消息"""
        pass

    @abstractmethod
    def parse_message(self, raw_payload: dict[str, Any]) -> Message | None:
        """解析原始消息"""
        pass

    def register_handler(self, handler: callable):
        """注册消息处理器"""
        self._handlers.append(handler)

    def _dispatch(self, message: Message):
        """分发消息到处理器"""
        for handler in self._handlers:
            try:
                handler(message)
            except Exception as e:
                logger.error(f"Handler error: {e}")


class QQAdapter(PlatformAdapter):
    """QQ 平台适配器"""

    PLATFORM_NAME = "qq"

    def __init__(self, config: PlatformConfig):
        super().__init__(config)
        self.api_base = "https://api.sgroup.qq.com"

    def send_message(self, channel_id: str, content: str) -> dict[str, Any]:
        """发送 QQ 消息"""
        if not self.config.bot_token:
            return {"success": False, "error": "No bot token configured"}

        headers = {
            "Authorization": f"Bot {self.config.bot_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "content": content,
        }

        try:
            import urllib.request

            url = f"{self.api_base}/channels/{channel_id}/messages"
            data = json.dumps(payload).encode("utf-8")

            req = urllib.request.Request(
                url,
                data=data,
                headers=headers,
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode())
                return {"success": True, "message_id": result.get("id")}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def parse_message(self, raw_payload: dict[str, Any]) -> Message | None:
        """解析 QQ 消息"""
        if not raw_payload:
            return None

        msg_type = raw_payload.get("type")
        if msg_type == 0:
            content = raw_payload.get("content", "")
            return Message(
                platform=self.PLATFORM_NAME,
                content=content,
                sender_id=str(raw_payload.get("author", {}).get("id", "")),
                sender_name=raw_payload.get("author", {}).get("username"),
                channel_id=str(raw_payload.get("channel_id", "")),
                timestamp=raw_payload.get("timestamp"),
                raw=raw_payload,
            )
        return None


class DiscordAdapter(PlatformAdapter):
    """Discord 平台适配器"""

    PLATFORM_NAME = "discord"
    API_BASE = "https://discord.com/api/v10"

    def send_message(self, channel_id: str, content: str) -> dict[str, Any]:
        """发送 Discord 消息"""
        if not self.config.bot_token:
            return {"success": False, "error": "No bot token configured"}

        headers = {
            "Authorization": f"Bot {self.config.bot_token}",
            "Content-Type": "application/json",
        }

        payload = {"content": content}

        try:
            import urllib.request

            url = f"{self.API_BASE}/channels/{channel_id}/messages"
            data = json.dumps(payload).encode("utf-8")

            req = urllib.request.Request(
                url,
                data=data,
                headers=headers,
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode())
                return {"success": True, "message_id": result.get("id")}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def parse_message(self, raw_payload: dict[str, Any]) -> Message | None:
        """解析 Discord 消息"""
        if not raw_payload:
            return None

        if raw_payload.get("type") == 0:
            return Message(
                platform=self.PLATFORM_NAME,
                content=raw_payload.get("content", ""),
                sender_id=str(raw_payload.get("author", {}).get("id", "")),
                sender_name=raw_payload.get("author", {}).get("username"),
                channel_id=str(raw_payload.get("channel_id", "")),
                timestamp=raw_payload.get("timestamp"),
                raw=raw_payload,
                attachments=raw_payload.get("attachments", []),
            )
        return None


class TelegramAdapter(PlatformAdapter):
    """Telegram 平台适配器"""

    PLATFORM_NAME = "telegram"
    API_BASE = "https://api.telegram.org"

    def send_message(self, channel_id: str, content: str) -> dict[str, Any]:
        """发送 Telegram 消息"""
        if not self.config.bot_token:
            return {"success": False, "error": "No bot token configured"}

        try:
            import urllib.parse
            import urllib.request

            url = f"{self.API_BASE}/bot{self.config.bot_token}/sendMessage"

            payload = {
                "chat_id": channel_id,
                "text": content,
                "parse_mode": "Markdown",
            }

            data = urllib.parse.urlencode(payload).encode("utf-8")

            req = urllib.request.Request(url, data=data, method="POST")

            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode())
                if result.get("ok"):
                    return {
                        "success": True,
                        "message_id": result.get("result", {}).get("message_id"),
                    }
                return {"success": False, "error": result.get("description")}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def parse_message(self, raw_payload: dict[str, Any]) -> Message | None:
        """解析 Telegram 消息"""
        if not raw_payload:
            return None

        message = raw_payload.get("message") or raw_payload.get("edited_message")
        if message:
            return Message(
                platform=self.PLATFORM_NAME,
                content=message.get("text", ""),
                sender_id=str(message.get("from", {}).get("id", "")),
                sender_name=message.get("from", {}).get("first_name"),
                channel_id=str(message.get("chat", {}).get("id", "")),
                timestamp=message.get("date"),
                raw=raw_payload,
            )
        return None


class PlatformManager:
    """平台管理器"""

    def __init__(self):
        self._adapters: dict[str, PlatformAdapter] = {}
        self._lock = threading.Lock()

    def register_adapter(self, platform: str, adapter: PlatformAdapter):
        """注册平台适配器"""
        with self._lock:
            self._adapters[platform] = adapter
            logger.info(f"Registered platform adapter: {platform}")

    def get_adapter(self, platform: str) -> PlatformAdapter | None:
        """获取平台适配器"""
        with self._lock:
            return self._adapters.get(platform)

    def send_to_platform(self, platform: str, channel_id: str, content: str) -> dict[str, Any]:
        """发送消息到指定平台"""
        adapter = self.get_adapter(platform)
        if not adapter:
            return {"success": False, "error": f"Unknown platform: {platform}"}
        return adapter.send_message(channel_id, content)

    def broadcast(
        self, platforms: list[str], channel_ids: list[str], content: str
    ) -> list[dict[str, Any]]:
        """广播消息到多个平台"""
        results = []
        for platform, channel_id in zip(platforms, channel_ids, strict=False):
            result = self.send_to_platform(platform, channel_id, content)
            results.append({"platform": platform, **result})
        return results


_platform_manager_instance: PlatformManager | None = None
_platform_lock = threading.Lock()


def get_platform_manager() -> PlatformManager:
    """获取全局平台管理器"""
    global _platform_manager_instance
    with _platform_lock:
        if _platform_manager_instance is None:
            _platform_manager_instance = PlatformManager()
        return _platform_manager_instance


def register_qq(config: PlatformConfig) -> QQAdapter:
    """注册 QQ 适配器"""
    adapter = QQAdapter(config)
    get_platform_manager().register_adapter("qq", adapter)
    return adapter


def register_discord(config: PlatformConfig) -> DiscordAdapter:
    """注册 Discord 适配器"""
    adapter = DiscordAdapter(config)
    get_platform_manager().register_adapter("discord", adapter)
    return adapter


def register_telegram(config: PlatformConfig) -> TelegramAdapter:
    """注册 Telegram 适配器"""
    adapter = TelegramAdapter(config)
    get_platform_manager().register_adapter("telegram", adapter)
    return adapter
