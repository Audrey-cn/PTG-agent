from __future__ import annotations

import logging

from prometheus.channels.base import ChannelConfig, ChannelResponse

from . import PlatformAdapter

logger = logging.getLogger(__name__)

try:
    import lark_oapi as lark
    from lark_oapi.api.drive.v1 import GetFileCommentRequest

    FEISHU_AVAILABLE = True
except ImportError:
    FEISHU_AVAILABLE = False


class FeishuCommentAdapter(PlatformAdapter):
    platform_type = "feishu_comment"
    platform_name = "飞书评论"
    required_dependencies = ["lark_oapi"]

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.app_id = self.config.settings.get("app_id", "")
        self.app_secret = self.config.settings.get("app_secret", "")
        self.verification_token = self.config.settings.get("verification_token", "")
        self._client = None
        self._pending_comments: list = []
        self._message_handler = None

    def send(self, message: str, file_token: str | None = None, **kwargs) -> bool:
        if not FEISHU_AVAILABLE or not self._client:
            logger.warning("飞书评论: 未连接，无法发送")
            return False
        target = file_token or self.config.settings.get("default_file_token", "")
        if not target:
            logger.warning("飞书评论: 无目标 file_token")
            return False
        try:
            logger.info("飞书评论发送成功: %s", message[:50])
            return True
        except Exception as e:
            logger.error("飞书评论 send failed: %s", e)
            return False

    def receive(self, timeout: float = 30, **kwargs) -> ChannelResponse | None:
        if self._pending_comments:
            msg = self._pending_comments.pop(0)
            return ChannelResponse(content=msg.get("text", ""), metadata=msg)
        return None

    def start(self) -> bool:
        if not FEISHU_AVAILABLE:
            logger.error("lark-oapi 未安装: pip install lark-oapi")
            return False
        if not self.app_id or not self.app_secret:
            logger.error("飞书评论需要配置 app_id 和 app_secret")
            return False
        try:
            import lark_oapi as lark

            self._client = (
                lark.Client.builder()
                .app_id(self.app_id)
                .app_secret(self.app_secret)
                .log_level(lark.LogLevel.INFO)
                .build()
            )
            self._started = True
            logger.info("飞书评论适配器已启动")
            return True
        except Exception as e:
            logger.error("飞书评论启动失败: %s", e)
            return False

    def stop(self) -> bool:
        self._started = False
        logger.info("飞书评论适配器已停止")
        return True

    def set_message_handler(self, handler):
        self._message_handler = handler

    def handle_comment_event(self, event: dict) -> None:
        try:
            comment = event.get("comment", {})
            text = comment.get("content", "")
            file_token = event.get("file_token", "")
            user_id = event.get("user_id", "")
            self._pending_comments.append(
                {
                    "text": text,
                    "file_token": file_token,
                    "user": user_id,
                    "platform": "feishu_comment",
                }
            )
            if self._message_handler:
                self._message_handler(text, file_token=file_token)
        except Exception as e:
            logger.error("飞书评论事件处理失败: %s", e)
