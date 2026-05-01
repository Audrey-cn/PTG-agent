from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, Optional

from prometheus.acp_adapter.auth import ACPAuth
from prometheus.acp_adapter.events import ACPEvents
from prometheus.acp_adapter.permissions import ACPPermissions
from prometheus.acp_adapter.tools import ACPTools

logger = logging.getLogger("prometheus.acp_adapter.entry")


class ACPEndpoint:
    def __init__(self) -> None:
        self.auth = ACPAuth()
        self.tools = ACPTools()
        self.permissions = ACPPermissions()
        self.events = ACPEvents()
        self._running = False
        self._server = None

    async def start_server(self, host: str = "localhost", port: int = 8765) -> None:
        self._running = True
        logger.info(f"Starting ACP server on {host}:{port}")

        self.events.emit("state_change", {"state": "starting", "host": host, "port": port})

        try:
            self._server = await asyncio.start_server(
                self._handle_client,
                host,
                port
            )
            self.events.emit("state_change", {"state": "running", "host": host, "port": port})

            async with self._server:
                await self._server.serve_forever()
        except Exception as e:
            logger.error(f"Server error: {e}")
            self.events.emit("error", {"error": str(e)})
            raise

    async def stop_server(self) -> None:
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        self.events.emit("state_change", {"state": "stopped"})
        logger.info("ACP server stopped")

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        addr = writer.get_extra_info('peername')
        logger.debug(f"Client connected: {addr}")

        try:
            while self._running:
                data = await reader.read(4096)
                if not data:
                    break

                response = await self._process_message(data)
                writer.write(response)
                await writer.drain()
        except Exception as e:
            logger.error(f"Client handler error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            logger.debug(f"Client disconnected: {addr}")

    async def _process_message(self, data: bytes) -> bytes:
        import json

        try:
            message = json.loads(data.decode())
            action = message.get("action")

            if action == "invoke_tool":
                result = self.tools.invoke_tool(
                    message.get("tool", ""),
                    message.get("params", {})
                )
                return json.dumps(result).encode()

            elif action == "list_tools":
                return json.dumps(self.tools.list_tools()).encode()

            elif action == "check_permission":
                allowed = self.permissions.check_permission(
                    message.get("agent_id", ""),
                    message.get("action", ""),
                    message.get("resource", "")
                )
                return json.dumps({"allowed": allowed}).encode()

            else:
                return json.dumps({"error": f"Unknown action: {action}"}).encode()

        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid JSON"}).encode()
        except Exception as e:
            return json.dumps({"error": str(e)}).encode()

    async def connect_to_server(self, server_url: str) -> None:
        logger.info(f"Connecting to ACP server: {server_url}")
        self.events.emit("state_change", {"state": "connecting", "url": server_url})

    async def send_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        import json

        if not self._server:
            return {"error": "Not connected to server"}

        return {"status": "sent"}


def run_acp_server(host: str = "localhost", port: int = 8765) -> None:
    endpoint = ACPEndpoint()
    asyncio.run(endpoint.start_server(host, port))


def run_acp_client(server_url: str) -> ACPEndpoint:
    endpoint = ACPEndpoint()
    asyncio.create_task(endpoint.connect_to_server(server_url))
    return endpoint
