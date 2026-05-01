from __future__ import annotations

import logging
from typing import Any

from prometheus.gateway.config import GatewayConfig, load_gateway_config
from prometheus.gateway.delivery import MessageDelivery
from prometheus.gateway.hooks import HookManager
from prometheus.gateway.session import SessionManager
from prometheus.gateway.status import StatusTracker

logger = logging.getLogger(__name__)


class GatewayRunner:
    def __init__(self) -> None:
        self._config: GatewayConfig | None = None
        self._session_manager: SessionManager | None = None
        self._delivery: MessageDelivery | None = None
        self._hook_manager: HookManager | None = None
        self._status_tracker: StatusTracker | None = None
        self._running = False

    def start(self, config: GatewayConfig | None = None) -> bool:
        if self._running:
            logger.warning("Gateway is already running")
            return False
        try:
            self._config = config or load_gateway_config()
            self._session_manager = SessionManager(self._config)
            self._delivery = MessageDelivery(self._session_manager)
            self._hook_manager = HookManager()
            self._status_tracker = StatusTracker()
            self._status_tracker.start()
            self._running = True
            logger.info("Gateway started on %s:%d", self._config.host, self._config.port)
            return True
        except Exception as e:
            logger.error("Failed to start gateway: %s", e)
            self._running = False
            return False

    def stop(self) -> bool:
        if not self._running:
            logger.warning("Gateway is not running")
            return False
        try:
            if self._session_manager:
                for session in self._session_manager.list_active():
                    self._session_manager.close_session(session.id)
            if self._status_tracker:
                self._status_tracker.stop()
            self._running = False
            logger.info("Gateway stopped")
            return True
        except Exception as e:
            logger.error("Failed to stop gateway: %s", e)
            return False

    def is_running(self) -> bool:
        return self._running

    def get_status(self) -> Dict[str, Any]:
        if not self._status_tracker:
            return {"running": False}
        status = self._status_tracker.get_status()
        if self._session_manager:
            status.active_sessions = len(self._session_manager.list_active())
            if self._status_tracker:
                self._status_tracker.set_active_sessions(status.active_sessions)
        return {
            "running": status.running,
            "started_at": status.started_at,
            "active_sessions": status.active_sessions,
            "messages_sent": status.messages_sent,
            "messages_received": status.messages_received,
            "errors": status.errors,
        }

    @property
    def session_manager(self) -> SessionManager | None:
        return self._session_manager

    @property
    def delivery(self) -> MessageDelivery | None:
        return self._delivery

    @property
    def hook_manager(self) -> HookManager | None:
        return self._hook_manager

    @property
    def status_tracker(self) -> StatusTracker | None:
        return self._status_tracker
