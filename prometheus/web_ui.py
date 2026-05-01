#!/usr/bin/env python3
"""Prometheus Web UI 基础框架."""

import json
import logging
from typing import Any

try:
    from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles
except ImportError:
    FastAPI = None
    WebSocket = None

logger = logging.getLogger("prometheus.webui")


class WebUIServer:
    """
    Web UI 服务器

    提供基于 FastAPI 的 Web 界面支持。
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._app = None
            cls._instance._clients: list[WebSocket] = []
            cls._instance._running = False
        return cls._instance

    def initialize(self):
        """初始化 Web UI 服务器"""
        if FastAPI is None:
            raise ImportError("fastapi library is required for WebUIServer")

        self._app = FastAPI(title="Prometheus Web UI", version="0.1.0")

        self._setup_routes()

    def _setup_routes(self):
        """设置路由"""

        @self._app.get("/", response_class=HTMLResponse)
        async def root():
            return self._get_index_html()

        @self._app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self._clients.append(websocket)

            try:
                while True:
                    data = await websocket.receive_text()
                    await self._handle_websocket_message(websocket, data)
            except WebSocketDisconnect:
                self._clients.remove(websocket)

        @self._app.post("/api/message")
        async def send_message(message: dict[str, Any]):
            content = message.get("content", "")
            await self._broadcast_message(content)
            return {"status": "success", "message": "Message sent"}

        @self._app.get("/api/status")
        async def get_status():
            return {
                "connected_clients": len(self._clients),
                "status": "running",
            }

    def _get_index_html(self) -> str:
        """获取索引页面"""
        html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prometheus Web UI</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 0;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
        }

        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }

        .header {
            text-align: center;
            padding: 40px 0;
        }

        .header h1 {
            color: #e94560;
            font-size: 2.5rem;
            margin: 0;
            font-weight: 700;
        }

        .header p {
            color: #8892b0;
            margin-top: 10px;
        }

        .chat-container {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            overflow: hidden;
        }

        .chat-messages {
            height: 500px;
            overflow-y: auto;
            padding: 20px;
        }

        .chat-messages::-webkit-scrollbar {
            width: 6px;
        }

        .chat-messages::-webkit-scrollbar-track {
            background: rgba(255, 255, 255, 0.05);
        }

        .chat-messages::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.2);
            border-radius: 3px;
        }

        .message {
            margin-bottom: 20px;
            display: flex;
            gap: 12px;
        }

        .message.assistant {
            flex-direction: row-reverse;
        }

        .avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }

        .user .avatar {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }

        .assistant .avatar {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
        }

        .message-content {
            max-width: 70%;
        }

        .user .message-content {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 16px 16px 4px 16px;
        }

        .assistant .message-content {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 16px 16px 16px 4px;
        }

        .message-content p {
            margin: 0;
            padding: 12px 16px;
            color: white;
            font-size: 14px;
            line-height: 1.6;
        }

        .input-container {
            padding: 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            display: flex;
            gap: 12px;
        }

        .input-container input {
            flex: 1;
            padding: 14px 18px;
            border: none;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.1);
            color: white;
            font-size: 14px;
            outline: none;
            transition: background 0.2s;
        }

        .input-container input:focus {
            background: rgba(255, 255, 255, 0.15);
        }

        .input-container input::placeholder {
            color: rgba(255, 255, 255, 0.4);
        }

        .input-container button {
            padding: 14px 24px;
            background: linear-gradient(135deg, #e94560 0%, #ff6b6b 100%);
            border: none;
            border-radius: 12px;
            color: white;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }

        .input-container button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 20px rgba(233, 69, 96, 0.4);
        }

        .status-bar {
            text-align: center;
            padding: 10px;
            color: rgba(255, 255, 255, 0.4);
            font-size: 12px;
        }

        .typing-indicator {
            display: flex;
            align-items: center;
            gap: 4px;
            padding: 8px 12px;
            color: rgba(255, 255, 255, 0.6);
        }

        .typing-indicator span {
            width: 6px;
            height: 6px;
            background: rgba(255, 255, 255, 0.6);
            border-radius: 50%;
            animation: typing 1.4s infinite ease-in-out;
        }

        .typing-indicator span:nth-child(2) {
            animation-delay: 0.2s;
        }

        .typing-indicator span:nth-child(3) {
            animation-delay: 0.4s;
        }

        @keyframes typing {
            0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; }
            40% { transform: scale(1); opacity: 1; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔥 Prometheus</h1>
            <p>Epic Chronicler - AI Agent System</p>
        </div>

        <div class="chat-container">
            <div class="chat-messages" id="chat-messages">
                <div class="message assistant">
                    <div class="avatar">P</div>
                    <div class="message-content">
                        <p>Hello! I'm Prometheus, your AI assistant. How can I help you today?</p>
                    </div>
                </div>
            </div>

            <div class="input-container">
                <input type="text" id="message-input" placeholder="Type a message..." onkeyup="handleKeyPress(event)">
                <button onclick="sendMessage()">Send</button>
            </div>
        </div>

        <div class="status-bar" id="status-bar">
            Connected - WebSocket
        </div>
    </div>

    <script>
        const ws = new WebSocket('ws://' + window.location.host + '/ws');

        ws.onopen = function() {
            document.getElementById('status-bar').textContent = 'Connected - WebSocket';
        };

        ws.onclose = function() {
            document.getElementById('status-bar').textContent = 'Disconnected';
        };

        ws.onmessage = function(event) {
            const message = JSON.parse(event.data);
            addMessage('assistant', message.content);
        };

        function sendMessage() {
            const input = document.getElementById('message-input');
            const content = input.value.trim();

            if (!content) return;

            addMessage('user', content);
            ws.send(JSON.stringify({ type: 'message', content: content }));
            input.value = '';
        }

        function handleKeyPress(event) {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                sendMessage();
            }
        }

        function addMessage(sender, content) {
            const container = document.getElementById('chat-messages');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message ' + sender;

            const avatar = document.createElement('div');
            avatar.className = 'avatar';
            avatar.textContent = sender === 'user' ? 'U' : 'P';

            const contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';
            contentDiv.innerHTML = '<p>' + escapeHtml(content) + '</p>';

            messageDiv.appendChild(avatar);
            messageDiv.appendChild(contentDiv);
            container.appendChild(messageDiv);

            container.scrollTop = container.scrollHeight;
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    </script>
</body>
</html>"""
        return html

    async def _handle_websocket_message(self, websocket: WebSocket, data: str):
        """处理 WebSocket 消息"""
        try:
            message = json.loads(data)
            logger.info(f"WebSocket message: {message.get('type', 'unknown')}")
        except json.JSONDecodeError:
            logger.error("Invalid WebSocket message")

    async def _broadcast_message(self, content: str):
        """广播消息到所有客户端"""
        for client in self._clients:
            try:
                await client.send_text(json.dumps({"type": "message", "content": content}))
            except Exception as e:
                logger.error(f"Failed to send to client: {e}")

    def get_app(self):
        """获取 FastAPI 应用实例"""
        if not self._app:
            self.initialize()
        return self._app

    def run(self, host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
        """运行服务器"""
        if not self._app:
            self.initialize()

        try:
            import uvicorn

            uvicorn.run(self._app, host=host, port=port, reload=reload)
        except ImportError:
            raise ImportError("uvicorn is required to run the web server")


def get_web_ui_server() -> WebUIServer:
    """获取全局 Web UI 服务器实例"""
    return WebUIServer()


if __name__ == "__main__":
    print("🌐 Web UI Server")
    print("=" * 50)

    try:
        server = get_web_ui_server()
        server.run(host="127.0.0.1", port=8000, reload=True)
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("Install with: pip install fastapi uvicorn")


def start_dashboard_server(
    host: str = "127.0.0.1",
    port: int = 9119,
    open_browser: bool = True,
    embedded_tui: bool = False,
) -> None:
    """启动 Dashboard Web 服务器。

    Args:
        host: 主机地址
        port: 端口
        open_browser: 是否自动打开浏览器
        embedded_tui: 是否启用嵌入式 TUI 聊天
    """
    import threading
    import webbrowser

    server = get_web_ui_server()
    server.initialize()

    if open_browser:

        def _open_browser():
            import time

            time.sleep(1.5)
            webbrowser.open(f"http://{host}:{port}")

        browser_thread = threading.Thread(target=_open_browser, daemon=True)
        browser_thread.start()

    logger.info(f"Starting dashboard server on {host}:{port}")
    server.run(host=host, port=port, reload=False)


def get_dashboard_stats() -> dict[str, Any]:
    """获取 Dashboard 统计数据。"""
    from prometheus.memory_system import MemorySystem
    from prometheus.session_manager import get_session_browser

    browser = get_session_browser()
    sessions = browser.list_sessions(limit=1000)

    try:
        memory = MemorySystem()
        memory_count = len(memory.get_all_memories())
    except Exception:
        memory_count = 0

    return {
        "sessions": {
            "total": len(sessions),
            "active": sum(1 for s in sessions if not s.end_reason),
        },
        "memory": {
            "total": memory_count,
        },
        "timestamp": datetime.now().isoformat(),
    }
