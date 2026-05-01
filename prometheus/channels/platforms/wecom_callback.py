from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Optional, Any

from prometheus.channels.base import ChannelConfig, ChannelResponse
from . import PlatformAdapter
from .wecom_crypto import decrypt, verify_signature

logger = logging.getLogger(__name__)


class WeComCallbackAdapter(PlatformAdapter):
    platform_type = "wecom_callback"
    platform_name = "企业微信回调"
    required_dependencies = []

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.token = self.config.settings.get("wecom_token", "")
        self.encoding_aes_key = self.config.settings.get("wecom_encoding_aes_key", "")
        self.corp_id = self.config.settings.get("corp_id", "")
        self._pending_messages: list = []
        self._message_handler = None

    def send(self, message: str, user: str | None = None, **kwargs) -> bool:
        logger.info("企业微信回调发送: %s", message[:50])
        return True

    def receive(self, timeout: float = 30, **kwargs) -> Optional[ChannelResponse]:
        if self._pending_messages:
            msg = self._pending_messages.pop(0)
            return ChannelResponse(content=msg.get("text", ""), metadata=msg)
        return None

    def start(self) -> bool:
        if not self.token or not self.encoding_aes_key:
            logger.error("企业微信回调需要配置 wecom_token 和 wecom_encoding_aes_key")
            return False
        self._started = True
        logger.info("企业微信回调适配器已启动")
        return True

    def stop(self) -> bool:
        self._started = False
        logger.info("企业微信回调适配器已停止")
        return True

    def set_message_handler(self, handler):
        self._message_handler = handler

    def verify_callback(self, signature: str, timestamp: str, nonce: str, echostr: str) -> str:
        if not verify_signature(signature, timestamp, nonce, self.token):
            logger.warning("企业微信回调验证失败")
            return ""
        try:
            decrypted = decrypt(echostr, self.encoding_aes_key)
            return decrypted
        except Exception as e:
            logger.error("企业微信回调解密失败: %s", e)
            return ""

    def handle_callback(self, signature: str, timestamp: str, nonce: str, body: str) -> Optional[str]:
        if not verify_signature(signature, timestamp, nonce, self.token):
            logger.warning("企业微信回调签名验证失败")
            return None
        try:
            decrypted = decrypt(body, self.encoding_aes_key)
            root = ET.fromstring(decrypted)
            msg_type = root.findtext("MsgType", "")
            content = root.findtext("Content", "")
            from_user = root.findtext("FromUserName", "")
            self._pending_messages.append({
                "text": content,
                "user": from_user,
                "msg_type": msg_type,
                "platform": "wecom_callback",
            })
            if self._message_handler:
                self._message_handler(content, user=from_user)
            return "success"
        except Exception as e:
            logger.error("企业微信回调处理失败: %s", e)
            return None
