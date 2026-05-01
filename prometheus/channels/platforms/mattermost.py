from __future__ import annotations

import json
import logging
import threading
import time
from typing import Optional, Any

import requests

from prometheus.channels.base import ChannelConfig, ChannelResponse
from . import PlatformAdapter

logger = logging.getLogger(__name__)


class MattermostAdapter(PlatformAdapter):
    platform_type = "mattermost"
    platform_name = "Mattermost"
    required_dependencies: list = []

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.server_url = self.config.settings.get("server_url", "")
        self.bot_token = self.config.settings.get("bot_token", "")
        self.team_name = self.config.settings.get("team_name", "default")
        self.allowed_channels = self.config.settings.get("allowed_channels", [])
        self._session = None
        self._user_id = ""
        self._pending_messages: list = []
        self._message_handler = None
        self._polling = False

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.bot_token}", "Content-Type": "application/json"}

    def send(self, message: str, channel_id: str | None = None, **kwargs) -> bool:
        if not self.bot_token:
            logger.warning("Mattermost: 未配置 bot_token，无法发送")
            return False
        target = channel_id or (self.allowed_channels[0] if self.allowed_channels else None)
        if not target:
            logger.warning("Mattermost: 无目标 channel")
            return False
        try:
            resp = requests.post(
                f"{self.server_url}/api/v4/posts",
                headers=self._headers(),
                json={"channel_id": target, "message": message[:16383]},
                timeout=10,
            )
            return resp.status_code == 201
        except Exception as e:
            logger.error("Mattermost send failed: %s", e)
            return False

    def receive(self, timeout: float = 30, **kwargs) -> Optional[ChannelResponse]:
        if self._pending_messages:
            msg = self._pending_messages.pop(0)
            return ChannelResponse(content=msg.get("text", ""), metadata=msg)
        return None

    def start(self) -> bool:
        if not self.server_url or not self.bot_token:
            logger.error("Mattermost 需要配置 server_url 和 bot_token")
            return False
        try:
            resp = requests.get(
                f"{self.server_url}/api/v4/users/me",
                headers=self._headers(),
                timeout=10,
            )
            if resp.status_code != 200:
                logger.error("Mattermost 认证失败: %s", resp.status_code)
                return False
            self._user_id = resp.json().get("id", "")
            self._session = requests.Session()
            self._session.headers.update(self._headers())
            self._started = True
            logger.info("Mattermost 适配器已启动")
            return True
        except Exception as e:
            logger.error("Mattermost 启动失败: %s", e)
            return False

    def stop(self) -> bool:
        self._polling = False
        if self._session:
            self._session.close()
        self._started = False
        logger.info("Mattermost 适配器已停止")
        return True

    def set_message_handler(self, handler):
        self._message_handler = handler
