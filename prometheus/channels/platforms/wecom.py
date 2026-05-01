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

_WECOM_API_BASE = "https://qyapi.weixin.qq.com/cgi-bin"


class WeComAdapter(PlatformAdapter):
    platform_type = "wecom"
    platform_name = "企业微信"
    required_dependencies: list = []

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.corp_id = self.config.settings.get("corp_id", "")
        self.corp_secret = self.config.settings.get("corp_secret", "")
        self.agent_id = self.config.settings.get("agent_id", "")
        self.webhook_url = self.config.settings.get("webhook_url", "")
        self._access_token = ""
        self._token_expires_at = 0.0
        self._pending_messages: list = []
        self._message_handler = None

    def _get_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token
        try:
            resp = requests.get(
                f"{_WECOM_API_BASE}/gettoken",
                params={"corpid": self.corp_id, "corpsecret": self.corp_secret},
                timeout=10,
            )
            data = resp.json()
            if data.get("errcode") == 0:
                self._access_token = data["access_token"]
                self._token_expires_at = time.time() + data.get("expires_in", 7200) - 300
                return self._access_token
            else:
                logger.error("企业微信获取 token 失败: %s", data.get("errmsg"))
                return ""
        except Exception as e:
            logger.error("企业微信获取 token 异常: %s", e)
            return ""

    def send(self, message: str, user: str | None = None, **kwargs) -> bool:
        if self.webhook_url:
            try:
                resp = requests.post(
                    self.webhook_url,
                    json={"msgtype": "text", "text": {"content": message}},
                    timeout=10,
                )
                data = resp.json()
                return data.get("errcode") == 0
            except Exception as e:
                logger.error("企业微信 webhook 发送失败: %s", e)
                return False

        token = self._get_access_token()
        if not token:
            logger.warning("企业微信: 无 access_token，无法发送")
            return False
        try:
            resp = requests.post(
                f"{_WECOM_API_BASE}/message/send",
                params={"access_token": token},
                json={
                    "touser": user or "@all",
                    "msgtype": "text",
                    "agentid": self.agent_id,
                    "text": {"content": message},
                },
                timeout=10,
            )
            data = resp.json()
            if data.get("errcode") == 0:
                return True
            else:
                logger.error("企业微信发送失败: %s", data.get("errmsg"))
                return False
        except Exception as e:
            logger.error("企业微信 send failed: %s", e)
            return False

    def receive(self, timeout: float = 30, **kwargs) -> Optional[ChannelResponse]:
        if self._pending_messages:
            msg = self._pending_messages.pop(0)
            return ChannelResponse(content=msg.get("text", ""), metadata=msg)
        return None

    def start(self) -> bool:
        if not self.corp_id and not self.webhook_url:
            logger.error("企业微信需要配置 corp_id/corp_secret 或 webhook_url")
            return False
        if self.corp_id and self.corp_secret:
            token = self._get_access_token()
            if not token:
                logger.error("企业微信获取 access_token 失败")
                return False
        self._started = True
        logger.info("企业微信适配器已启动")
        return True

    def stop(self) -> bool:
        self._started = False
        logger.info("企业微信适配器已停止")
        return True

    def set_message_handler(self, handler):
        self._message_handler = handler
