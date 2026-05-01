import logging

from prometheus.channels.base import ChannelConfig, ChannelResponse

from . import PlatformAdapter

logger = logging.getLogger(__name__)

try:
    import dingtalk_stream

    DINGTALK_AVAILABLE = True
except ImportError:
    DINGTALK_AVAILABLE = False


class DingtalkAdapter(PlatformAdapter):
    platform_type = "dingtalk"
    platform_name = "钉钉"
    required_dependencies = ["dingtalk_stream"]

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.client_id = self.config.settings.get("client_id", "")
        self.client_secret = self.config.settings.get("client_secret", "")
        self._client = None
        self._pending_messages: list = []
        self._message_handler = None

    def send(self, message: str, conversation_id: str | None = None, **kwargs) -> bool:
        if not DINGTALK_AVAILABLE:
            logger.warning("钉钉: dingtalk-stream 未安装")
            return False
        logger.info("钉钉发送: %s...", message[:50])
        return True

    def receive(self, timeout: float = 30, **kwargs) -> ChannelResponse | None:
        if self._pending_messages:
            msg = self._pending_messages.pop(0)
            return ChannelResponse(content=msg.get("text", ""), metadata=msg)
        return None

    def start(self) -> bool:
        if not DINGTALK_AVAILABLE:
            logger.error("dingtalk-stream 未安装: pip install dingtalk-stream")
            return False
        if not self.client_id or not self.client_secret:
            logger.error("钉钉需要配置 client_id 和 client_secret")
            return False
        try:
            self._is_running = True
            logger.info("钉钉适配器已初始化")
            return True
        except Exception as e:
            logger.error("钉钉启动失败: %s", e)
            return False

    def stop(self) -> bool:
        self._is_running = False
        logger.info("钉钉适配器已停止")
        return True

    def set_message_handler(self, handler):
        self._message_handler = handler
