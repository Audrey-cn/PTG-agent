from __future__ import annotations

import hashlib
import hmac
import logging

from prometheus.channels.base import ChannelConfig, ChannelResponse

from . import PlatformAdapter

logger = logging.getLogger(__name__)


class MattermostSlashAdapter(PlatformAdapter):
    platform_type = "mattermost_slash"
    platform_name = "Mattermost Slash"
    required_dependencies = []

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.webhook_secret = self.config.settings.get("webhook_secret", "")
        self.default_channel_id = self.config.settings.get("default_channel_id", "")
        self.webhook_url = self.config.settings.get("webhook_url", "")
        self._pending_commands: list = []
        self._message_handler = None

    def send(self, message: str, channel_id: str | None = None, **kwargs) -> bool:
        target = channel_id or self.default_channel_id
        if not target and not self.webhook_url:
            logger.warning("Mattermost Slash: 无目标 channel_id 或 webhook_url")
            return False
        logger.info("Mattermost Slash 发送: %s", message[:50])
        return True

    def receive(self, timeout: float = 30, **kwargs) -> ChannelResponse | None:
        if self._pending_commands:
            msg = self._pending_commands.pop(0)
            return ChannelResponse(content=msg.get("text", ""), metadata=msg)
        return None

    def start(self) -> bool:
        self._started = True
        logger.info("Mattermost Slash 适配器已启动")
        return True

    def stop(self) -> bool:
        self._started = False
        logger.info("Mattermost Slash 适配器已停止")
        return True

    def set_message_handler(self, handler):
        self._message_handler = handler

    def verify_request(self, signature: str, timestamp: str, body: str) -> bool:
        if not self.webhook_secret:
            return True
        expected = hmac.new(
            self.webhook_secret.encode("utf-8"),
            f"{timestamp}:{body}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def handle_slash_command(self, request_data: dict) -> dict:
        if not self._started:
            return {"text": "Adapter not started", "response_type": "ephemeral"}
        command = request_data.get("command", "")
        text = request_data.get("text", "")
        user_id = request_data.get("user_id", "")
        user_name = request_data.get("user_name", "")
        channel_id = request_data.get("channel_id", "")
        team_domain = request_data.get("team_domain", "")
        self._pending_commands.append(
            {
                "text": text,
                "command": command,
                "user_id": user_id,
                "user_name": user_name,
                "channel_id": channel_id,
                "team_domain": team_domain,
                "platform": "mattermost_slash",
            }
        )
        if self._message_handler:
            try:
                response = self._message_handler(text, channel_id=channel_id, user_id=user_id)
                if response:
                    return {
                        "text": str(response),
                        "response_type": "in_channel",
                    }
            except Exception as e:
                logger.error("Mattermost Slash handler error: %s", e)
                return {"text": f"Error: {e}", "response_type": "ephemeral"}
        return {
            "text": f"Command '{command}' received",
            "response_type": "ephemeral",
        }
