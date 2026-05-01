"""Prometheus TUI Gateway - Python Backend."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from websockets.exceptions import ConnectionClosed
from websockets.server import WebSocketServerProtocol, serve

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger("prometheus.tui_gateway")


@dataclass
class TUISession:
    """TUI 会话"""

    id: str
    session_id: str
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    message_count: int = 0


@dataclass
class TUIState:
    """TUI 状态"""

    sessions: dict[str, TUISession] = field(default_factory=dict)
    active_session: str | None = None


class TUIWebSocketHandler:
    """WebSocket 消息处理器"""

    def __init__(self, state: TUIState):
        self.state = state
        self._handlers: dict[str, Callable] = {
            "session.start": self._handle_session_start,
            "session.send": self._handle_session_send,
            "session.end": self._handle_session_end,
            "ping": self._handle_ping,
        }

    async def handle(self, websocket: WebSocketServerProtocol, message: dict[str, Any]):
        """处理 WebSocket 消息"""
        msg_type = message.get("type")
        handler = self._handlers.get(msg_type)

        if not handler:
            await self._send_error(websocket, f"Unknown message type: {msg_type}")
            return

        try:
            await handler(websocket, message)
        except Exception as e:
            logger.error(f"Handler error for {msg_type}: {e}")
            await self._send_error(websocket, str(e))

    async def _handle_session_start(
        self,
        websocket: WebSocketServerProtocol,
        message: dict[str, Any],
    ):
        """开始新会话"""
        session_id = str(uuid.uuid4())
        tui_session = TUISession(
            id=message.get("id", session_id),
            session_id=session_id,
        )
        self.state.sessions[session_id] = tui_session
        self.state.active_session = session_id

        await self._send(
            websocket,
            {
                "type": "session.started",
                "session_id": session_id,
            },
        )

    async def _handle_session_send(
        self,
        websocket: WebSocketServerProtocol,
        message: dict[str, Any],
    ):
        """发送消息"""
        session_id = message.get("session_id")
        message.get("content", "")

        if not session_id or session_id not in self.state.sessions:
            await self._send_error(websocket, "Invalid session")
            return

        session = self.state.sessions[session_id]
        session.message_count += 1
        session.last_active = datetime.now()

        await self._send(
            websocket,
            {
                "type": "message.sent",
                "session_id": session_id,
            },
        )

    async def _handle_session_end(
        self,
        websocket: WebSocketServerProtocol,
        message: dict[str, Any],
    ):
        """结束会话"""
        session_id = message.get("session_id")

        if session_id and session_id in self.state.sessions:
            del self.state.sessions[session_id]

        if self.state.active_session == session_id:
            self.state.active_session = None

        await self._send(websocket, {"type": "session.ended"})

    async def _handle_ping(self, websocket: WebSocketServerProtocol, message: dict[str, Any]):
        """处理 ping"""
        await self._send(websocket, {"type": "pong"})

    async def _send(self, websocket: WebSocketServerProtocol, data: dict[str, Any]):
        """发送消息"""
        with contextlib.suppress(ConnectionClosed):
            await websocket.send(json.dumps(data))

    async def _send_error(self, websocket: WebSocketServerProtocol, error: str):
        """发送错误"""
        await self._send(websocket, {"type": "error", "error": error})


class TUIGateway:
    """TUI Gateway 主类"""

    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.state = TUIState()
        self.handler = TUIWebSocketHandler(self.state)
        self._server = None

    async def _websocket_handler(self, websocket: WebSocketServerProtocol, path: str):
        """WebSocket 连接处理器"""
        logger.info(f"New TUI connection from {websocket.remote_address}")

        try:
            async for raw_message in websocket:
                try:
                    message = json.loads(raw_message)
                    await self.handler.handle(websocket, message)
                except json.JSONDecodeError:
                    await self.handler._send_error(websocket, "Invalid JSON")
        except ConnectionClosed:
            logger.info("TUI connection closed")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")

    async def start(self):
        """启动 Gateway"""
        self._server = await serve(
            self._websocket_handler,
            self.host,
            self.port,
        )
        logger.info(f"TUI Gateway started on ws://{self.host}:{self.port}")

    async def stop(self):
        """停止 Gateway"""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        logger.info("TUI Gateway stopped")

    def get_status(self) -> dict[str, Any]:
        """获取状态"""
        return {
            "host": self.host,
            "port": self.port,
            "active_sessions": len(self.state.sessions),
            "active_session": self.state.active_session,
        }


async def main():
    """主入口"""
    gateway = TUIGateway()
    await gateway.start()
    print(f"TUI Gateway running on ws://localhost:{gateway.port}")
    print("Press Ctrl+C to stop")

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        await gateway.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
