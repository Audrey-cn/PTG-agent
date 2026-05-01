import json
import logging
from typing import Optional, Any

from prometheus.channels.base import ChannelConfig, ChannelResponse
from . import PlatformAdapter

logger = logging.getLogger(__name__)

try:
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import (
        CreateMessageRequest,
        CreateMessageRequestBody,
        ReceiveMessageEvent,
    )
    FEISHU_AVAILABLE = True
except ImportError:
    FEISHU_AVAILABLE = False


class FeishuAdapter(PlatformAdapter):
    platform_type = "feishu"
    platform_name = "飞书"
    required_dependencies = ["lark_oapi"]

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.app_id = self.config.settings.get("app_id", "")
        self.app_secret = self.config.settings.get("app_secret", "")
        self.verification_token = self.config.settings.get("verification_token", "")
        self.encrypt_key = self.config.settings.get("encrypt_key", "")
        self._client = None
        self._pending_messages: list = []
        self._message_handler = None

    def send(self, message: str, chat_id: str | None = None, **kwargs) -> bool:
        if not FEISHU_AVAILABLE or not self._client:
            logger.warning("飞书: 未连接，无法发送")
            return False
        target = chat_id or self.config.settings.get("default_chat_id", "")
        if not target:
            logger.warning("飞书: 无目标 chat_id")
            return False
        try:
            import lark_oapi as lark
            from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

            body = CreateMessageRequestBody.builder() \
                .msg_type("text") \
                .content(json.dumps({"text": message})) \
                .build()
            req = CreateMessageRequest.builder() \
                .receive_id_type("chat_id") \
                .request_body(body) \
                .build()
            resp = self._client.im.v1.message.create(req)
            if resp.success():
                return True
            else:
                logger.error("飞书发送失败: %s %s", resp.code, resp.msg)
                return False
        except Exception as e:
            logger.error("飞书 send failed: %s", e)
            return False

    def receive(self, timeout: float = 30, **kwargs) -> Optional[ChannelResponse]:
        if self._pending_messages:
            msg = self._pending_messages.pop(0)
            return ChannelResponse(content=msg.get("text", ""), metadata=msg)
        return None

    def start(self) -> bool:
        if not FEISHU_AVAILABLE:
            logger.error("lark-oapi 未安装: pip install lark-oapi")
            return False
        if not self.app_id or not self.app_secret:
            logger.error("飞书需要配置 app_id 和 app_secret")
            return False
        try:
            import lark_oapi as lark
            self._client = lark.Client.builder() \
                .app_id(self.app_id) \
                .app_secret(self.app_secret) \
                .log_level(lark.LogLevel.DEBUG) \
                .build()

            event_handler = lark.EventDispatcherHandler.builder(
                verification_token=self.verification_token,
                encrypt_key=self.encrypt_key,
            ) \
            .register_p2_im_message_receive_v1(self._on_message) \
            .build()

            self._cli = lark.Cli.builder() \
                .app_id(self.app_id) \
                .app_secret(self.app_secret) \
            .build()

            self._is_running = True
            logger.info("飞书适配器已初始化（需 webhook 或长连接启动）")
            return True
        except Exception as e:
            logger.error("飞书启动失败: %s", e)
            return False

    def stop(self) -> bool:
        self._is_running = False
        logger.info("飞书适配器已停止")
        return True

    def _on_message(self, data: ReceiveMessageEvent) -> None:
        try:
            msg = data.event.message
            content = json.loads(msg.content) if msg.content else {}
            text = content.get("text", "")
            chat_id = msg.chat_id
            self._pending_messages.append({
                "text": text,
                "chat_id": chat_id,
                "user": data.event.sender.sender_id.user_id,
                "platform": "feishu",
            })
            if self._message_handler:
                self._message_handler(text, chat_id=chat_id)
        except Exception as e:
            logger.error("飞书消息处理失败: %s", e)

    def set_message_handler(self, handler):
        self._message_handler = handler
