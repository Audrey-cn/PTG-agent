#!/usr/bin/env python3
"""Prometheus TUI Gateway 系统."""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

try:
    import websockets
except ImportError:
    websockets = None

logger = logging.getLogger("prometheus.tui")


class MessageType(Enum):
    TEXT = "text"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    SYSTEM = "system"
    STATUS = "status"
    ERROR = "error"


class GatewayState(Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    AUTHENTICATING = "authenticating"
    READY = "ready"


@dataclass
class TUIConnection:
    """TUI 连接"""

    connection_id: str
    websocket: Any
    state: str = GatewayState.CONNECTED.value
    last_activity: str = ""
    session_data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.last_activity = datetime.now().isoformat()


@dataclass
class TUIMessage:
    """TUI 消息"""

    message_id: str
    type: str
    content: str
    sender: str = ""
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class TUIGateway:
    """
    TUI 网关服务器

    提供 WebSocket 接口，支持 TUI 客户端连接。
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._connections: dict[str, TUIConnection] = {}
            cls._instance._message_queue: asyncio.Queue = asyncio.Queue()
            cls._instance._running = False
            cls._instance._server = None
        return cls._instance

    async def start(self, host: str = "127.0.0.1", port: int = 8765):
        """启动网关服务器"""
        if websockets is None:
            raise ImportError("websockets library is required for TUIGateway")

        self._running = True

        async def handler(websocket, path):
            await self._handle_connection(websocket)

        self._server = await websockets.serve(handler, host, port)
        logger.info(f"TUI Gateway started on ws://{host}:{port}")

        await self._server.wait_closed()

    async def stop(self):
        """停止网关服务器"""
        self._running = False

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        for conn in self._connections.values():
            await conn.websocket.close()

        logger.info("TUI Gateway stopped")

    async def _handle_connection(self, websocket):
        """处理单个连接"""
        connection_id = str(uuid.uuid4())[:8]

        conn = TUIConnection(
            connection_id=connection_id,
            websocket=websocket,
        )
        self._connections[connection_id] = conn

        logger.info(f"New TUI connection: {connection_id}")

        try:
            async for message in websocket:
                conn.last_activity = datetime.now().isoformat()
                await self._process_message(connection_id, message)

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            del self._connections[connection_id]
            logger.info(f"TUI connection closed: {connection_id}")

    async def _process_message(self, connection_id: str, message_str: str):
        """处理收到的消息"""
        try:
            message = json.loads(message_str)

            message_type = message.get("type")
            content = message.get("content", "")

            if message_type == "ping":
                await self._send_pong(connection_id)

            elif message_type == "message":
                await self._handle_client_message(connection_id, content)

            elif message_type == "tool_call":
                await self._handle_tool_call(connection_id, content)

            elif message_type == "auth":
                await self._handle_auth(connection_id, content)

            else:
                logger.warning(f"Unknown message type: {message_type}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON message: {e}")

    async def _send_pong(self, connection_id: str):
        """发送 pong 响应"""
        await self._send_message(connection_id, "pong", "")

    async def _handle_client_message(self, connection_id: str, content: str):
        """处理客户端消息"""
        logger.info(f"Received message from {connection_id}: {content[:100]}")

        await self._send_message(connection_id, "status", "Message received")

    async def _handle_tool_call(self, connection_id: str, content: str):
        """处理工具调用"""
        try:
            tool_call = json.loads(content)
            logger.info(f"Tool call from {connection_id}: {tool_call.get('name', 'unknown')}")

            await self._send_message(connection_id, "status", "Tool call processing")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid tool call: {e}")

    async def _handle_auth(self, connection_id: str, content: str):
        """处理认证"""
        logger.info(f"Auth attempt from {connection_id}")
        await self._send_message(connection_id, "status", "Authenticated")

    async def _send_message(self, connection_id: str, message_type: str, content: str, **metadata):
        """发送消息到客户端"""
        if connection_id not in self._connections:
            return

        conn = self._connections[connection_id]

        message = {
            "message_id": str(uuid.uuid4())[:8],
            "type": message_type,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **metadata,
        }

        try:
            await conn.websocket.send(json.dumps(message))
        except Exception as e:
            logger.error(f"Failed to send message to {connection_id}: {e}")

    async def broadcast(self, message_type: str, content: str, **metadata):
        """广播消息到所有客户端"""
        for connection_id in list(self._connections.keys()):
            await self._send_message(connection_id, message_type, content, **metadata)

    def get_connection_count(self) -> int:
        """获取当前连接数"""
        return len(self._connections)

    def get_status(self) -> dict[str, Any]:
        """获取网关状态"""
        return {
            "running": self._running,
            "connections": self.get_connection_count(),
        }


def get_tui_gateway() -> TUIGateway:
    """获取全局 TUI 网关实例"""
    return TUIGateway()


async def run_tui_gateway(host: str = "127.0.0.1", port: int = 8765):
    """运行 TUI 网关"""
    gateway = get_tui_gateway()
    await gateway.start(host, port)


if __name__ == "__main__":
    print("🚀 TUI Gateway")
    print("=" * 50)

    try:
        asyncio.run(run_tui_gateway())
    except ImportError:
        print("❌ websockets library not installed")
        print("Install with: pip install websockets")
    except KeyboardInterrupt:
        print("\n👋 Gateway stopped")
