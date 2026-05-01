"""ACP (Agent Communication Protocol) server for Prometheus."""

import asyncio
import json
import logging
import uuid
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("prometheus.acp")

ACP_DEFAULT_PORT = 8747
ACP_PROTOCOL_VERSION = "1.0"


class ACPMessage:
    """ACP message types."""

    HANDSHAKE = "handshake"
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class ACPClient:
    """ACP client connection."""

    def __init__(
        self,
        client_id: str,
        websocket,
        identity: dict[str, Any] | None = None,
    ):
        self.client_id = client_id
        self.websocket = websocket
        self.identity = identity or {}
        self.session_id = str(uuid.uuid4())[:8]
        self.is_authenticated = False


class ACPMessageHandler:
    """Handler for ACP messages."""

    def __init__(self):
        self._handlers: dict[str, Callable] = {}

    def register(self, message_type: str, handler: Callable):
        """Register a message handler."""
        self._handlers[message_type] = handler

    async def handle(self, client: ACPClient, message: dict[str, Any]) -> dict[str, Any] | None:
        """Handle a message."""
        message_type = message.get("type", "")
        handler = self._handlers.get(message_type)

        if handler:
            return await handler(client, message)

        return {"type": "error", "error": f"Unknown message type: {message_type}"}


class ACPServer:
    """ACP server for agent-to-agent communication.

    Allows multiple Prometheus instances to communicate and delegate tasks.
    """

    def __init__(
        self,
        port: int = ACP_DEFAULT_PORT,
        identity: dict[str, Any] | None = None,
    ):
        self.port = port
        self.identity = identity or {
            "name": "Prometheus",
            "version": "0.8.0",
            "protocol_version": ACP_PROTOCOL_VERSION,
        }
        self._clients: dict[str, ACPClient] = {}
        self._handler = ACPMessageHandler()
        self._running = False
        self._server = None

        self._setup_handlers()

    def _setup_handlers(self):
        """Set up message handlers."""
        self._handler.register(ACPMessage.HANDSHAKE, self._handle_handshake)
        self._handler.register(ACPMessage.REQUEST, self._handle_request)
        self._handler.register(ACPMessage.HEARTBEAT, self._handle_heartbeat)

    async def _handle_handshake(
        self,
        client: ACPClient,
        message: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle client handshake."""
        client.identity = message.get("identity", {})
        client.is_authenticated = True

        return {
            "type": "handshake_ack",
            "server_identity": self.identity,
            "client_session_id": client.session_id,
        }

    async def _handle_request(
        self,
        client: ACPClient,
        message: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle agent request."""
        request_id = message.get("request_id", str(uuid.uuid4())[:8])
        action = message.get("action", "")
        message.get("payload", {})

        logger.info(f"ACP request from {client.client_id}: {action}")

        return {
            "type": "response",
            "request_id": request_id,
            "status": "ok",
            "payload": {"result": "processed"},
        }

    async def _handle_heartbeat(
        self,
        client: ACPClient,
        message: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle heartbeat."""
        return {"type": "heartbeat_ack"}

    async def _handle_connection(self, websocket, path: str):
        """Handle a client connection."""
        client_id = str(uuid.uuid4())[:8]
        client = ACPClient(client_id, websocket)

        self._clients[client_id] = client
        logger.info(f"New ACP connection: {client_id}")

        try:
            async for raw_message in websocket:
                try:
                    message = json.loads(raw_message)
                    response = await self._handler.handle(client, message)

                    if response:
                        await websocket.send(json.dumps(response))

                except json.JSONDecodeError:
                    await websocket.send(
                        json.dumps(
                            {
                                "type": "error",
                                "error": "Invalid JSON",
                            }
                        )
                    )

        except Exception as e:
            logger.error(f"ACP connection error: {e}")

        finally:
            if client_id in self._clients:
                del self._clients[client_id]
            logger.info(f"ACP connection closed: {client_id}")

    async def start(self):
        """Start the ACP server."""
        try:
            import websockets

            async def handler(websocket, path):
                await self._handle_connection(websocket, path)

            self._server = await websockets.serve(handler, "0.0.0.0", self.port)
            self._running = True
            logger.info(f"ACP server started on port {self.port}")

            await asyncio.Future()

        except ImportError:
            logger.error("websockets library required for ACP server")
        except Exception as e:
            logger.error(f"Failed to start ACP server: {e}")

    async def stop(self):
        """Stop the ACP server."""
        self._running = False

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        logger.info("ACP server stopped")

    def get_status(self) -> dict[str, Any]:
        """Get server status."""
        return {
            "running": self._running,
            "port": self.port,
            "identity": self.identity,
            "connected_clients": len(self._clients),
        }


class ACPClientManager:
    """Manager for ACP client connections."""

    def __init__(self):
        self._connections: dict[str, ACPClient] = {}

    async def connect(
        self,
        host: str,
        port: int,
        identity: dict[str, Any] | None = None,
    ) -> str | None:
        """Connect to an ACP server.

        Returns:
            Connection ID if successful
        """
        try:
            import websockets

            uri = f"ws://{host}:{port}"
            websocket = await websockets.connect(uri)

            connection_id = str(uuid.uuid4())[:8]

            handshake = {
                "type": "handshake",
                "identity": identity
                or {
                    "name": "Prometheus",
                    "version": "0.8.0",
                },
            }

            await websocket.send(json.dumps(handshake))
            response = json.loads(await websocket.recv())

            if response.get("type") == "handshake_ack":
                self._connections[connection_id] = websocket
                return connection_id

        except Exception as e:
            logger.error(f"Failed to connect to ACP server: {e}")

        return None

    async def send_request(
        self,
        connection_id: str,
        action: str,
        payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Send a request to a connected server.

        Returns:
            Response payload if successful
        """
        websocket = self._connections.get(connection_id)
        if not websocket:
            return None

        try:
            request = {
                "type": "request",
                "request_id": str(uuid.uuid4())[:8],
                "action": action,
                "payload": payload,
            }

            await websocket.send(json.dumps(request))
            response = json.loads(await websocket.recv())

            if response.get("type") == "response":
                return response.get("payload")

        except Exception as e:
            logger.error(f"ACP request failed: {e}")

        return None

    async def disconnect(self, connection_id: str):
        """Disconnect from a server."""
        if connection_id in self._connections:
            websocket = self._connections[connection_id]
            await websocket.close()
            del self._connections[connection_id]


async def run_acp_server(port: int = ACP_DEFAULT_PORT):
    """Run the ACP server.

    Args:
        port: Port to listen on
    """
    server = ACPServer(port=port)
    await server.start()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Prometheus ACP Server")
    parser.add_argument("--port", type=int, default=ACP_DEFAULT_PORT, help="Port to listen on")

    args = parser.parse_args()

    asyncio.run(run_acp_server(args.port))
