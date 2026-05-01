from __future__ import annotations

import contextlib
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from prometheus.channels.base import ChannelConfig, ChannelResponse

from . import PlatformAdapter

logger = logging.getLogger(__name__)


class WebhookAdapter(PlatformAdapter):
    platform_type = "webhook"
    platform_name = "HTTP Webhook"
    required_dependencies: list = []

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.host = self.config.settings.get("host", "0.0.0.0")
        self.port = int(self.config.settings.get("port", 9090))
        self.path = self.config.settings.get("path", "/webhook")
        self._server = None
        self._thread = None
        self._pending_messages: list = []
        self._message_handler = None

    def send(self, message: str, url: str | None = None, **kwargs) -> bool:
        if not url:
            logger.warning("Webhook: 无目标 URL")
            return False
        try:
            import requests

            resp = requests.post(url, json={"content": message}, timeout=10)
            return resp.status_code < 400
        except Exception as e:
            logger.error("Webhook send failed: %s", e)
            return False

    def receive(self, timeout: float = 30, **kwargs) -> ChannelResponse | None:
        if self._pending_messages:
            msg = self._pending_messages.pop(0)
            return ChannelResponse(content=msg.get("text", ""), metadata=msg)
        return None

    def start(self) -> bool:
        try:
            adapter = self

            class WebhookHandler(BaseHTTPRequestHandler):
                def do_GET(self):
                    parsed = urlparse(self.path)
                    if parsed.path == adapter.path:
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps({"status": "ok"}).encode())
                    else:
                        self.send_response(404)
                        self.end_headers()

                def do_POST(self):
                    parsed = urlparse(self.path)
                    if parsed.path != adapter.path:
                        self.send_response(404)
                        self.end_headers()
                        return
                    content_length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(content_length)
                    try:
                        data = json.loads(body) if body else {}
                    except json.JSONDecodeError:
                        data = {"raw": body.decode("utf-8", errors="replace")}

                    text = data.get("text", data.get("content", data.get("message", "")))
                    sender = data.get("sender", data.get("user", "webhook"))

                    adapter._pending_messages.append(
                        {
                            "text": str(text),
                            "sender": sender,
                            "platform": "webhook",
                            "raw_data": data,
                        }
                    )

                    if adapter._message_handler:
                        try:
                            adapter._message_handler(str(text), data=data)
                        except Exception as e:
                            logger.error("Webhook message handler error: %s", e)

                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "accepted"}).encode())

                def log_message(self, format, *args):
                    logger.debug("Webhook: %s", format % args)

            self._server = HTTPServer((self.host, self.port), WebhookHandler)

            def _run():
                self._server.serve_forever()

            self._thread = threading.Thread(target=_run, daemon=True)
            self._thread.start()
            self._started = True
            logger.info("Webhook 适配器已启动: http://%s:%d%s", self.host, self.port, self.path)
            return True
        except Exception as e:
            logger.error("Webhook 启动失败: %s", e)
            return False

    def stop(self) -> bool:
        if self._server:
            with contextlib.suppress(Exception):
                self._server.shutdown()
        self._started = False
        logger.info("Webhook 适配器已停止")
        return True

    def set_message_handler(self, handler):
        self._message_handler = handler
