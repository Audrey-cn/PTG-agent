from __future__ import annotations

import json
import logging
from typing import Optional
from urllib.request import urlopen
from urllib.error import URLError

logger = logging.getLogger(__name__)

try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False


class BrowserConnection:
    def __init__(self) -> None:
        self._endpoint: str = ""
        self._ws: Optional[object] = None
        self._connected: bool = False
        self._status: dict = {}

    def connect(self, endpoint_url: str = "http://localhost:9222") -> bool:
        if self._connected:
            logger.warning("Already connected to %s", self._endpoint)
            return False

        self._endpoint = endpoint_url.rstrip("/")

        try:
            with urlopen(f"{self._endpoint}/json/version", timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self._status = data
        except URLError as e:
            logger.error("Cannot reach CDP endpoint %s: %s", self._endpoint, e)
            return False
        except Exception as e:
            logger.error("Failed to connect to %s: %s", self._endpoint, e)
            return False

        ws_url = data.get("webSocketDebuggerUrl")
        if ws_url and WEBSOCKET_AVAILABLE:
            try:
                self._ws = websocket.create_connection(ws_url, timeout=5)
            except Exception as e:
                logger.warning("WebSocket connection failed: %s, falling back to HTTP only", e)
                self._ws = None

        self._connected = True
        return True

    def disconnect(self) -> bool:
        if not self._connected:
            return False
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None
        self._connected = False
        self._status = {}
        return True

    def is_connected(self) -> bool:
        return self._connected

    def get_status(self) -> dict:
        if not self._connected:
            return {"connected": False}
        result = {"connected": True, "endpoint": self._endpoint}
        result.update(self._status)
        return result

    def list_tabs(self) -> list[dict]:
        if not self._connected:
            return []
        try:
            with urlopen(f"{self._endpoint}/json", timeout=5) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.error("Failed to list tabs: %s", e)
            return []
