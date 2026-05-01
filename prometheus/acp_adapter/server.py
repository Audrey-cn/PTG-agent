from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("prometheus.acp_adapter.server")


class ACPServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        self._host = host
        self._port = port
        self._running = False

    def start(self, host: str | None = None, port: int | None = None) -> None:
        self._host = host or self._host
        self._port = port or self._port
        self._running = True
        logger.info("ACP server starting on %s:%s", self._host, self._port)

    def stop(self) -> None:
        self._running = False
        logger.info("ACP server stopped")

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        action = request.get("action", "")
        payload = request.get("payload", {})

        if not action:
            return {"status": "error", "message": "Missing action field"}

        try:
            result = self._dispatch(action, payload)
            return {"status": "ok", "data": result}
        except Exception as exc:
            logger.error("Request handling failed: %s", exc)
            return {"status": "error", "message": str(exc)}

    def _dispatch(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        handlers = {
            "ping": self._handle_ping,
            "status": self._handle_status,
        }

        handler = handlers.get(action)
        if handler is None:
            raise ValueError(f"Unknown action: {action}")

        return handler(payload)

    def _handle_ping(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"pong": True}

    def _handle_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"running": self._running, "host": self._host, "port": self._port}
