from __future__ import annotations

import json
import logging
import threading
import time
from typing import Optional, Any

from prometheus.channels.base import ChannelConfig, ChannelResponse
from . import PlatformAdapter

logger = logging.getLogger(__name__)

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False


class QQAdapter(PlatformAdapter):
    platform_type = "qq"
    platform_name = "QQ Bot"
    required_dependencies = ["websockets"]

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.access_token = self.config.settings.get("access_token", "")
        self.ws_url = self.config.settings.get("ws_url", "ws://127.0.0.1:8080")
        self.bot_qq = self.config.settings.get("bot_qq", "")
        self._ws = None
        self._thread = None
        self._pending_messages: list = []
        self._message_handler = None

    def send(self, message: str, user_id: str | None = None, group_id: str | None = None, **kwargs) -> bool:
        if not self._ws:
            logger.warning("QQ Bot: 未连接，无法发送")
            return False
        logger.info("QQ Bot 发送: %s", message[:50])
        return True

    def receive(self, timeout: float = 30, **kwargs) -> Optional[ChannelResponse]:
        if self._pending_messages:
            msg = self._pending_messages.pop(0)
            return ChannelResponse(content=msg.get("text", ""), metadata=msg)
        return None

    def start(self) -> bool:
        if not WEBSOCKETS_AVAILABLE:
            logger.warning("websockets 未安装，QQ Bot 使用 placeholder 模式")
            self._started = True
            logger.info("QQ Bot 适配器已启动（placeholder 模式）")
            return True
        self._started = True
        logger.info("QQ Bot 适配器已启动")
        return True

    def stop(self) -> bool:
        self._started = False
        logger.info("QQ Bot 适配器已停止")
        return True

    def set_message_handler(self, handler):
        self._message_handler = handler

    def handle_event(self, event_data: dict) -> None:
        post_type = event_data.get("post_type", "")
        if post_type == "message":
            message_type = event_data.get("message_type", "")
            raw_message = event_data.get("raw_message", "")
            user_id = str(event_data.get("user_id", ""))
            group_id = str(event_data.get("group_id", "")) if message_type == "group" else ""
            self._pending_messages.append({
                "text": raw_message,
                "user_id": user_id,
                "group_id": group_id,
                "message_type": message_type,
                "platform": "qq",
            })
            if self._message_handler:
                self._message_handler(
                    raw_message,
                    user_id=user_id,
                    group_id=group_id,
                )
