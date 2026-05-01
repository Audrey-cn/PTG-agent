from __future__ import annotations

import json
import logging

from prometheus.channels.base import ChannelConfig, ChannelResponse

from . import PlatformAdapter

logger = logging.getLogger(__name__)

try:
    from slack_bolt import App as SlackApp

    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False


class SlackEventsAdapter(PlatformAdapter):
    platform_type = "slack_events"
    platform_name = "Slack Events"
    required_dependencies = ["slack_bolt"]

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.bot_token = self.config.settings.get("bot_token", "")
        self.signing_secret = self.config.settings.get("signing_secret", "")
        self.allowed_channels = self.config.settings.get("allowed_channels", [])
        self._app = None
        self._pending_events: list = []
        self._message_handler = None

    def send(self, message: str, channel: str | None = None, **kwargs) -> bool:
        if not SLACK_AVAILABLE or not self._app:
            logger.warning("Slack Events: 未连接，无法发送")
            return False
        target = channel or (self.allowed_channels[0] if self.allowed_channels else None)
        if not target:
            logger.warning("Slack Events: 无目标 channel")
            return False
        try:
            self._app.client.chat_postMessage(
                channel=target,
                text=message[:40000],
            )
            return True
        except Exception as e:
            logger.error("Slack Events send failed: %s", e)
            return False

    def receive(self, timeout: float = 30, **kwargs) -> ChannelResponse | None:
        if self._pending_events:
            msg = self._pending_events.pop(0)
            return ChannelResponse(content=msg.get("text", ""), metadata=msg)
        return None

    def start(self) -> bool:
        if not SLACK_AVAILABLE:
            logger.error("slack-bolt 未安装: pip install slack-bolt")
            return False
        if not self.bot_token or not self.signing_secret:
            logger.error("Slack Events 需要配置 bot_token 和 signing_secret")
            return False
        try:
            self._app = SlackApp(token=self.bot_token, signing_secret=self.signing_secret)
            self._started = True
            logger.info("Slack Events 适配器已启动")
            return True
        except Exception as e:
            logger.error("Slack Events 启动失败: %s", e)
            return False

    def stop(self) -> bool:
        self._started = False
        logger.info("Slack Events 适配器已停止")
        return True

    def set_message_handler(self, handler):
        self._message_handler = handler

    def handle_url_verification(self, challenge: str) -> dict:
        return {"challenge": challenge}

    def handle_event(self, event_data: dict) -> str | None:
        if not self._started:
            return None
        event_type = event_data.get("type", "")
        if event_type == "url_verification":
            return json.dumps(self.handle_url_verification(event_data.get("challenge", "")))
        event = event_data.get("event", {})
        event_type_inner = event.get("type", "")
        if event_type_inner == "message":
            text = event.get("text", "")
            channel_id = event.get("channel", "")
            user = event.get("user", "")
            if self.allowed_channels and channel_id not in self.allowed_channels:
                return "ignored"
            self._pending_events.append(
                {
                    "text": text,
                    "channel": channel_id,
                    "user": user,
                    "event_type": event_type_inner,
                    "platform": "slack_events",
                }
            )
            if self._message_handler:
                self._message_handler(text, channel=channel_id)
        return "ok"
