from __future__ import annotations

import logging
import threading
from typing import Optional, Any

from prometheus.channels.base import ChannelConfig, ChannelResponse
from . import PlatformAdapter

logger = logging.getLogger(__name__)

try:
    from matrix_client.client import MatrixClient as MatrixLibClient
    from matrix_client.room import Room
    MATRIX_AVAILABLE = True
except ImportError:
    MATRIX_AVAILABLE = False


class MatrixAdapter(PlatformAdapter):
    platform_type = "matrix"
    platform_name = "Matrix"
    required_dependencies = ["matrix_client"]

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.homeserver = self.config.settings.get("homeserver", "https://matrix.org")
        self.user_id = self.config.settings.get("user_id", "")
        self.access_token = self.config.settings.get("access_token", "")
        self.allowed_rooms = self.config.settings.get("allowed_rooms", [])
        self._client = None
        self._pending_messages: list = []
        self._message_handler = None

    def send(self, message: str, room_id: str | None = None, **kwargs) -> bool:
        if not MATRIX_AVAILABLE or not self._client:
            logger.warning("Matrix: 未连接，无法发送")
            return False
        target = room_id or (self.allowed_rooms[0] if self.allowed_rooms else None)
        if not target:
            logger.warning("Matrix: 无目标 room")
            return False
        try:
            room = self._client.rooms.get(target)
            if not room:
                room = self._client.join_room(target)
            room.send_text(message)
            return True
        except Exception as e:
            logger.error("Matrix send failed: %s", e)
            return False

    def receive(self, timeout: float = 30, **kwargs) -> Optional[ChannelResponse]:
        if self._pending_messages:
            msg = self._pending_messages.pop(0)
            return ChannelResponse(content=msg.get("text", ""), metadata=msg)
        return None

    def start(self) -> bool:
        if not MATRIX_AVAILABLE:
            logger.error("matrix-client 未安装: pip install matrix-client")
            return False
        if not self.homeserver or not self.access_token:
            logger.error("Matrix 需要配置 homeserver 和 access_token")
            return False
        try:
            self._client = MatrixLibClient(self.homeserver)
            self._client.login_with_token(self.access_token)

            def _on_message(room, event):
                if event["type"] != "m.room.message":
                    return
                if event.get("sender") == self.user_id:
                    return
                text = event.get("content", {}).get("body", "")
                self._pending_messages.append({
                    "text": text,
                    "room_id": room.room_id,
                    "user": event.get("sender", ""),
                    "platform": "matrix",
                })
                if self._message_handler:
                    try:
                        self._message_handler(text, room_id=room.room_id)
                    except Exception as e:
                        logger.error("Matrix message handler error: %s", e)

            self._client.add_listener(_on_message)

            for room_id in self.allowed_rooms:
                try:
                    self._client.join_room(room_id)
                except Exception as e:
                    logger.warning("Matrix 加入房间 %s 失败: %s", room_id, e)

            def _run():
                self._client.listen_forever()

            self._thread = threading.Thread(target=_run, daemon=True)
            self._thread.start()
            self._started = True
            logger.info("Matrix 适配器已启动")
            return True
        except Exception as e:
            logger.error("Matrix 启动失败: %s", e)
            return False

    def stop(self) -> bool:
        if self._client:
            try:
                self._client.stop_listener_thread()
            except Exception:
                pass
        self._started = False
        logger.info("Matrix 适配器已停止")
        return True

    def set_message_handler(self, handler):
        self._message_handler = handler
