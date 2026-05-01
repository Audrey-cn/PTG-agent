from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from . import PlatformAdapter

if TYPE_CHECKING:
    from prometheus.channels.base import ChannelConfig, ChannelResponse

logger = logging.getLogger(__name__)


class SignalAdapter(PlatformAdapter):
    platform_type = "signal"
    platform_name = "Signal"
    required_dependencies: list = []

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self._pending_messages: list = []
        self._message_handler = None

    def send(self, message: str, **kwargs) -> bool:
        logger.warning("Signal: not yet implemented")
        return False

    def receive(self, timeout: float = 30, **kwargs) -> ChannelResponse | None:
        logger.warning("Signal: not yet implemented")
        return None

    def start(self) -> bool:
        logger.warning("Signal: not yet implemented")
        return False

    def stop(self) -> bool:
        self._started = False
        return True

    def set_message_handler(self, handler):
        self._message_handler = handler
