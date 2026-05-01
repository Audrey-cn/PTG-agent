from __future__ import annotations

import json
import logging
from typing import Optional, Any

from prometheus.channels.base import ChannelConfig, ChannelResponse
from . import PlatformAdapter

logger = logging.getLogger(__name__)


class YuanbaoAdapter(PlatformAdapter):
    platform_type = "yuanbao"
    platform_name = "元宝"
    required_dependencies = []

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.api_key = self.config.settings.get("api_key", "")
        self.api_base = self.config.settings.get("api_base", "https://yuanbao.tencent.com/api")
        self.default_session = self.config.settings.get("default_session", "")
        self._pending_messages: list = []
        self._message_handler = None

    def send(self, message: str, session_id: str | None = None, **kwargs) -> bool:
        if not self.api_key:
            logger.warning("元宝: 未配置 api_key，无法发送")
            return False
        target = session_id or self.default_session
        if not target:
            logger.warning("元宝: 无目标 session_id")
            return False
        logger.info("元宝发送: %s", message[:50])
        return True

    def receive(self, timeout: float = 30, **kwargs) -> Optional[ChannelResponse]:
        if self._pending_messages:
            msg = self._pending_messages.pop(0)
            return ChannelResponse(content=msg.get("text", ""), metadata=msg)
        return None

    def start(self) -> bool:
        if not self.api_key:
            logger.warning("元宝未配置 api_key，使用 placeholder 模式")
        self._started = True
        logger.info("元宝适配器已启动")
        return True

    def stop(self) -> bool:
        self._started = False
        logger.info("元宝适配器已停止")
        return True

    def set_message_handler(self, handler):
        self._message_handler = handler

    def handle_webhook(self, event_data: dict) -> Optional[str]:
        if not self._started:
            return None
        event_type = event_data.get("type", "")
        if event_type == "message":
            message = event_data.get("content", "")
            session_id = event_data.get("session_id", "")
            user_id = event_data.get("user_id", "")
            self._pending_messages.append({
                "text": message,
                "session_id": session_id,
                "user_id": user_id,
                "platform": "yuanbao",
            })
            if self._message_handler:
                self._message_handler(message, session_id=session_id)
            return "ok"
        return "ignored"
