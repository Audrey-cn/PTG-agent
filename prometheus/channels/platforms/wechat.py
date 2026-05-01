from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from . import PlatformAdapter

if TYPE_CHECKING:
    from prometheus.channels.base import ChannelConfig, ChannelResponse

logger = logging.getLogger(__name__)


class WeChatAdapter(PlatformAdapter):
    platform_type = "wechat"
    platform_name = "微信"
    required_dependencies: list = []

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self._pending_messages: list = []
        self._message_handler = None

    def send(self, message: str, **kwargs) -> bool:
        logger.warning("微信: not yet implemented — 集成 wechaty 后可用")
        return False

    def receive(self, timeout: float = 30, **kwargs) -> ChannelResponse | None:
        logger.warning("微信: not yet implemented — 集成 wechaty 后可用")
        return None

    def start(self) -> bool:
        logger.warning("微信: not yet implemented — 需 wechaty puppet 支持")
        return False

    def stop(self) -> bool:
        self._started = False
        return True

    def set_message_handler(self, handler):
        self._message_handler = handler
