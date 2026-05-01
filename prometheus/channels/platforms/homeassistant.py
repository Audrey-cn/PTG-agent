from __future__ import annotations

import logging

from prometheus.channels.base import ChannelConfig, ChannelResponse

from . import PlatformAdapter

logger = logging.getLogger(__name__)

try:
    import websockets

    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False


class HomeAssistantAdapter(PlatformAdapter):
    platform_type = "homeassistant"
    platform_name = "Home Assistant"
    required_dependencies = ["websockets"]

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.ha_url = self.config.settings.get("ha_url", "ws://homeassistant.local:8123")
        self.access_token = self.config.settings.get("access_token", "")
        self.subscribe_entities = self.config.settings.get("subscribe_entities", [])
        self._ws = None
        self._thread = None
        self._message_id = 1
        self._pending_messages: list = []
        self._message_handler = None

    def send(
        self, message: str, entity_id: str | None = None, service: str | None = None, **kwargs
    ) -> bool:
        if not self._ws:
            logger.warning("Home Assistant: 未连接，无法发送")
            return False
        logger.info("Home Assistant 发送: %s", message[:50])
        return True

    def receive(self, timeout: float = 30, **kwargs) -> ChannelResponse | None:
        if self._pending_messages:
            msg = self._pending_messages.pop(0)
            return ChannelResponse(content=msg.get("text", ""), metadata=msg)
        return None

    def start(self) -> bool:
        if not WEBSOCKETS_AVAILABLE:
            logger.warning("websockets 未安装，Home Assistant 使用 placeholder 模式")
            self._started = True
            logger.info("Home Assistant 适配器已启动（placeholder 模式）")
            return True
        if not self.access_token:
            logger.warning("Home Assistant 未配置 access_token，使用 placeholder 模式")
            self._started = True
            return True
        self._started = True
        logger.info("Home Assistant 适配器已启动")
        return True

    def stop(self) -> bool:
        self._started = False
        logger.info("Home Assistant 适配器已停止")
        return True

    def set_message_handler(self, handler):
        self._message_handler = handler

    def handle_state_change(self, event_data: dict) -> None:
        entity_id = event_data.get("entity_id", "")
        new_state = event_data.get("new_state", {})
        old_state = event_data.get("old_state", {})
        if self.subscribe_entities and entity_id not in self.subscribe_entities:
            return
        state_value = new_state.get("state", "") if new_state else ""
        attributes = new_state.get("attributes", {}) if new_state else {}
        self._pending_messages.append(
            {
                "text": f"{entity_id}: {state_value}",
                "entity_id": entity_id,
                "state": state_value,
                "attributes": attributes,
                "old_state": old_state.get("state") if old_state else None,
                "platform": "homeassistant",
            }
        )
        if self._message_handler:
            self._message_handler(
                f"{entity_id}: {state_value}",
                entity_id=entity_id,
                state=state_value,
            )

    def call_service(self, domain: str, service: str, entity_id: str, **kwargs) -> bool:
        if not self._started:
            logger.warning("Home Assistant: 适配器未启动")
            return False
        logger.info("Home Assistant 调用服务: %s.%s for %s", domain, service, entity_id)
        return True
