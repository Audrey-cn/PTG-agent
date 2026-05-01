from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from prometheus.channels.base import ChannelConfig, ChannelResponse

from . import PlatformAdapter

logger = logging.getLogger(__name__)


class EmailChannelAdapter(PlatformAdapter):
    platform_type = "email"
    platform_name = "Email"
    required_dependencies: list = []

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.smtp_host = self.config.settings.get("smtp_host", "localhost")
        self.smtp_port = int(self.config.settings.get("smtp_port", 587))
        self.smtp_user = self.config.settings.get("smtp_user", "")
        self.smtp_password = self.config.settings.get("smtp_password", "")
        self.use_tls = self.config.settings.get("use_tls", True)
        self.from_addr = self.config.settings.get("from_addr", self.smtp_user)
        self.default_to = self.config.settings.get("default_to", "")
        self._pending_messages: list = []
        self._message_handler = None

    def send(
        self, message: str, to: str | None = None, subject: str | None = None, **kwargs
    ) -> bool:
        target = to or self.default_to
        if not target:
            logger.warning("Email: 无收件人")
            return False
        try:
            msg = MIMEMultipart()
            msg["From"] = self.from_addr
            msg["To"] = target
            msg["Subject"] = subject or "Prometheus Notification"
            msg.attach(MIMEText(message, "plain", "utf-8"))

            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=30)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30)

            if self.use_tls and self.smtp_port != 465:
                server.starttls()

            if self.smtp_user and self.smtp_password:
                server.login(self.smtp_user, self.smtp_password)

            server.sendmail(self.from_addr, target.split(","), msg.as_string())
            server.quit()
            return True
        except Exception as e:
            logger.error("Email send failed: %s", e)
            return False

    def receive(self, timeout: float = 30, **kwargs) -> ChannelResponse | None:
        if self._pending_messages:
            msg = self._pending_messages.pop(0)
            return ChannelResponse(content=msg.get("text", ""), metadata=msg)
        return None

    def start(self) -> bool:
        if not self.smtp_host:
            logger.error("Email 需要配置 smtp_host")
            return False
        try:
            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=10)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10)
            if self.use_tls and self.smtp_port != 465:
                server.starttls()
            if self.smtp_user and self.smtp_password:
                server.login(self.smtp_user, self.smtp_password)
            server.quit()
            self._started = True
            logger.info("Email 适配器已启动 (SMTP 连接验证通过)")
            return True
        except Exception as e:
            logger.error("Email SMTP 连接失败: %s", e)
            return False

    def stop(self) -> bool:
        self._started = False
        logger.info("Email 适配器已停止")
        return True

    def set_message_handler(self, handler):
        self._message_handler = handler
