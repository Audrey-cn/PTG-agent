from __future__ import annotations

import contextlib
import logging
import threading

from prometheus.channels.base import ChannelConfig, ChannelResponse

from . import PlatformAdapter

logger = logging.getLogger(__name__)

try:
    from slack_bolt import App as SlackApp
    from slack_bolt.adapter.socket_mode import SocketModeHandler

    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False


class SlackSocketAdapter(PlatformAdapter):
    platform_type = "slack_socket"
    platform_name = "Slack Socket Mode"
    required_dependencies = ["slack_bolt"]

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.bot_token = self.config.settings.get("bot_token", "")
        self.app_token = self.config.settings.get("app_token", "")
        self.allowed_channels = self.config.settings.get("allowed_channels", [])
        self._app = None
        self._handler = None
        self._thread = None
        self._pending_messages: list = []
        self._message_handler = None

    def send(self, message: str, channel: str | None = None, **kwargs) -> bool:
        if not SLACK_AVAILABLE or not self._app:
            logger.warning("Slack Socket: 未连接，无法发送")
            return False
        target = channel or (self.allowed_channels[0] if self.allowed_channels else None)
        if not target:
            logger.warning("Slack Socket: 无目标 channel")
            return False
        try:
            self._app.client.chat_postMessage(
                channel=target,
                text=message[:40000],
            )
            return True
        except Exception as e:
            logger.error("Slack Socket send failed: %s", e)
            return False

    def receive(self, timeout: float = 30, **kwargs) -> ChannelResponse | None:
        if self._pending_messages:
            msg = self._pending_messages.pop(0)
            return ChannelResponse(content=msg.get("text", ""), metadata=msg)
        return None

    def start(self) -> bool:
        if not SLACK_AVAILABLE:
            logger.error("slack-bolt 未安装: pip install slack-bolt")
            return False
        if not self.bot_token or not self.app_token:
            logger.error("Slack Socket 需要配置 bot_token 和 app_token")
            return False
        try:
            self._app = SlackApp(token=self.bot_token)

            @self._app.event("message")
            def _on_message(event, say):
                text = event.get("text", "")
                channel_id = event.get("channel", "")
                user = event.get("user", "")
                if self.allowed_channels and channel_id not in self.allowed_channels:
                    return
                self._pending_messages.append(
                    {
                        "text": text,
                        "channel": channel_id,
                        "user": user,
                        "platform": "slack_socket",
                    }
                )
                if self._message_handler:
                    try:
                        response = self._message_handler(text, channel=channel_id)
                        if response:
                            say(str(response)[:40000])
                    except Exception as e:
                        logger.error("Slack Socket message handler error: %s", e)

            self._handler = SocketModeHandler(self._app, self.app_token)

            def _run():
                self._handler.start()

            self._thread = threading.Thread(target=_run, daemon=True)
            self._thread.start()
            self._started = True
            logger.info("Slack Socket 适配器已启动")
            return True
        except Exception as e:
            logger.error("Slack Socket 启动失败: %s", e)
            return False

    def stop(self) -> bool:
        if self._handler:
            with contextlib.suppress(Exception):
                self._handler.close()
        self._started = False
        logger.info("Slack Socket 适配器已停止")
        return True

    def set_message_handler(self, handler):
        self._message_handler = handler
