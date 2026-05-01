"""Gateway daemon for Prometheus."""

import asyncio
import contextlib
import logging
import os
import threading
from pathlib import Path
from typing import Any

from prometheus._paths import get_paths

logger = logging.getLogger("prometheus.gateway")

DAEMON_STATUS_FILE = get_paths().home / "gateway" / "daemon_status.json"


class GatewayDaemon:
    """Gateway daemon manager.

    Manages the gateway as a background service with start/stop/status commands.
    """

    def __init__(self, config_path: str | None = None):
        self._config_path = config_path or str(get_paths().home / "gateway" / "config.yaml")
        self._status_file = DAEMON_STATUS_FILE
        self._process: threading.Thread | None = None
        self._shutdown_event = threading.Event()
        self._is_running = False

    def _ensure_status_dir(self):
        """Ensure the status directory exists."""
        self._status_file.parent.mkdir(parents=True, exist_ok=True)

    def _write_status(self, status: dict[str, Any]):
        """Write daemon status to file."""
        import json

        self._ensure_status_dir()
        try:
            with open(self._status_file, "w") as f:
                json.dump(status, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write status: {e}")

    def _read_status(self) -> dict[str, Any] | None:
        """Read daemon status from file."""
        import json

        if not self._status_file.exists():
            return None

        try:
            with open(self._status_file) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read status: {e}")
            return None

    def start(self, background: bool = True, port: int = 8765):
        """Start the gateway daemon.

        Args:
            background: Run in background if True
            port: Port to run the gateway on
        """
        if self.is_running():
            print("Gateway is already running")
            return

        print(f"Starting Prometheus Gateway on port {port}...")

        if background:
            self._process = threading.Thread(target=self._run_gateway, args=(port,), daemon=True)
            self._process.start()

            self._write_status(
                {
                    "status": "running",
                    "port": port,
                    "pid": os.getpid(),
                }
            )

            print(f"Gateway started in background (PID: {os.getpid()})")
        else:
            self._run_gateway(port)

    def _run_gateway(self, port: int):
        """Run the gateway server."""
        try:
            import websockets
            from websockets.server import serve

            async def handler(websocket, path):
                await self._handle_connection(websocket, path)

            async def run():
                async with serve(handler, "0.0.0.0", port):
                    self._is_running = True
                    logger.info(f"Gateway listening on port {port}")
                    await asyncio.Future()

            asyncio.run(run())

        except ImportError:
            logger.error("websockets library not installed. Run: pip install websockets")
            print("Error: websockets library required for gateway mode")
        except Exception as e:
            logger.error(f"Gateway error: {e}")
            self._is_running = False

    async def _handle_connection(self, websocket, path):
        """Handle a gateway connection."""
        try:
            async for message in websocket:
                await websocket.send(f"Echo: {message}")
        except Exception as e:
            logger.error(f"Connection error: {e}")

    def stop(self):
        """Stop the gateway daemon."""
        status = self._read_status()

        if not status or status.get("status") != "running":
            print("Gateway is not running")
            return

        print("Stopping Prometheus Gateway...")

        self._shutdown_event.set()
        self._is_running = False

        self._write_status(
            {
                "status": "stopped",
            }
        )

        print("Gateway stopped")

    def status(self) -> dict[str, Any]:
        """Get gateway daemon status."""
        status = self._read_status()

        if not status:
            return {"status": "not_initialized"}

        return {
            "status": status.get("status", "unknown"),
            "port": status.get("port"),
            "pid": status.get("pid"),
        }

    def is_running(self) -> bool:
        """Check if the gateway is running."""
        status = self._read_status()
        return status is not None and status.get("status") == "running"

    def restart(self, port: int | None = None):
        """Restart the gateway daemon."""
        if self.is_running():
            self.stop()

        import time

        time.sleep(1)

        self.start(background=True, port=port or 8765)


def get_gateway_daemon() -> GatewayDaemon:
    """Get a GatewayDaemon instance."""
    return GatewayDaemon()


async def run_gateway_server(host: str = "0.0.0.0", port: int = 8765):
    """Run gateway server as async server.

    Args:
        host: Host to bind to
        port: Port to listen on
    """
    try:
        import websockets
        from websockets.server import serve

        connections = set()

        async def handler(websocket):
            connections.add(websocket)
            try:
                async for message in websocket:
                    logger.info(f"Gateway received: {message[:100]}")
                    await websocket.send(f"Processed: {message}")
            finally:
                connections.remove(websocket)

        async def broadcast(message: str):
            for conn in connections:
                with contextlib.suppress(Exception):
                    await conn.send(message)

        async with serve(handler, host, port):
            logger.info(f"Gateway server started on {host}:{port}")
            await asyncio.Future()

    except ImportError:
        raise ImportError("websockets library required. Install with: pip install websockets")


def install_gateway_service():
    """Install gateway as a system service (platform-specific)."""
    import platform

    system = platform.system()

    if system == "Linux":
        install_linux_service()
    elif system == "Darwin":
        install_macos_service()
    elif system == "Windows":
        install_windows_service()
    else:
        print(f"Service installation not supported on {system}")


def install_linux_service():
    """Install as systemd service."""

    service_path = Path("/etc/systemd/system/prometheus-gateway.service")
    print(
        f"To install, run:\nsudo cp prometheus-gateway.service {service_path}\nsudo systemctl daemon-reload\nsudo systemctl enable prometheus-gateway"
    )


def install_macos_service():
    """Install as launchd service."""
    print("macOS service installation requires creating a plist file in ~/Library/LaunchAgents/")
    print(
        "See: https://developer.apple.com/library/content/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdPlists.html"
    )


def install_windows_service():
    """Install as Windows service."""
    print("Windows service installation requires pywin32. Run: pip install pywin32")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Prometheus Gateway Daemon")
    parser.add_argument(
        "command", choices=["start", "stop", "restart", "status", "install"], help="Command to run"
    )
    parser.add_argument("--port", type=int, default=8765, help="Port to run on")

    args = parser.parse_args()

    daemon = get_gateway_daemon()

    if args.command == "start":
        daemon.start(background=True, port=args.port)
    elif args.command == "stop":
        daemon.stop()
    elif args.command == "restart":
        daemon.restart(port=args.port)
    elif args.command == "status":
        import json

        print(json.dumps(daemon.status(), indent=2))
    elif args.command == "install":
        install_gateway_service()
