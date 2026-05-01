from __future__ import annotations

import logging

from prometheus.channels.base import ChannelConfig, ChannelResponse

from . import PlatformAdapter

logger = logging.getLogger(__name__)

try:
    from twilio.rest import Client as TwilioClient

    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False


class SmsAdapter(PlatformAdapter):
    platform_type = "sms"
    platform_name = "SMS"
    required_dependencies = ["twilio"]

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.account_sid = self.config.settings.get("account_sid", "")
        self.auth_token = self.config.settings.get("auth_token", "")
        self.from_number = self.config.settings.get("from_number", "")
        self.default_to = self.config.settings.get("default_to", "")
        self._client = None
        self._pending_messages: list = []
        self._message_handler = None

    def send(self, message: str, to: str | None = None, **kwargs) -> bool:
        if not TWILIO_AVAILABLE or not self._client:
            logger.warning("SMS: 未连接，无法发送")
            return False
        target = to or self.default_to
        if not target:
            logger.warning("SMS: 无目标号码")
            return False
        try:
            self._client.messages.create(
                body=message[:1600],
                from_=self.from_number,
                to=target,
            )
            return True
        except Exception as e:
            logger.error("SMS send failed: %s", e)
            return False

    def receive(self, timeout: float = 30, **kwargs) -> ChannelResponse | None:
        if self._pending_messages:
            msg = self._pending_messages.pop(0)
            return ChannelResponse(content=msg.get("text", ""), metadata=msg)
        return None

    def start(self) -> bool:
        if not TWILIO_AVAILABLE:
            logger.error("twilio 未安装: pip install twilio")
            return False
        if not self.account_sid or not self.auth_token:
            logger.error("SMS 需要配置 account_sid 和 auth_token")
            return False
        try:
            self._client = TwilioClient(self.account_sid, self.auth_token)
            self._started = True
            logger.info("SMS 适配器已启动")
            return True
        except Exception as e:
            logger.error("SMS 启动失败: %s", e)
            return False

    def stop(self) -> bool:
        self._client = None
        self._started = False
        logger.info("SMS 适配器已停止")
        return True

    def set_message_handler(self, handler):
        self._message_handler = handler
