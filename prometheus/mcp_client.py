#!/usr/bin/env python3
"""Prometheus MCP (Model Context Protocol) 集成模块."""

import json
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("prometheus.mcp")


class McpTransport(Enum):
    STDIO = "stdio"
    HTTP = "http"
    WEBSOCKET = "websocket"


@dataclass
class McpServerConfig:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    transport: McpTransport = McpTransport.STDIO
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class McpToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str


@dataclass
class McpToolCall:
    tool: McpToolDefinition
    arguments: dict[str, Any]


class McpClient:
    """
    MCP 客户端

    连接 MCP 服务器，发现工具，调用工具。
    """

    def __init__(self, config: McpServerConfig):
        self.config = config
        self._tools: dict[str, McpToolDefinition] = {}
        self._process = None
        self._lock = threading.Lock()
        self._connected = False

    def connect(self, timeout: float = 30.0) -> bool:
        """连接到 MCP 服务器"""
        with self._lock:
            if self._connected:
                return True

            try:
                if self.config.transport == McpTransport.STDIO:
                    return self._connect_stdio(timeout)
                elif self.config.transport == McpTransport.HTTP:
                    return self._connect_http()
                elif self.config.transport == McpTransport.WEBSOCKET:
                    return self._connect_websocket()
                else:
                    logger.error(f"Unknown transport: {self.config.transport}")
                    return False
            except Exception as e:
                logger.error(f"Failed to connect to MCP server {self.config.name}: {e}")
                return False

    def _connect_stdio(self, timeout: float) -> bool:
        """通过 STDIO 连接"""
        try:
            import subprocess

            env = dict(os.environ)
            env.update(self.config.env)

            self._process = subprocess.Popen(
                [self.config.command] + self.config.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )

            initialize_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "prometheus",
                        "version": "0.8.0",
                    },
                },
            }

            self._send_jsonrpc(initialize_request)
            response = self._read_jsonrpc(timeout=timeout)

            if response and response.get("result"):
                self._connected = True
                self._discover_tools()
                return True

            return False

        except Exception as e:
            logger.error(f"STDIO connection failed: {e}")
            return False

    def _connect_http(self) -> bool:
        """通过 HTTP 连接"""
        logger.info(f"HTTP MCP connection to {self.config.url} not yet implemented")
        return False

    def _connect_websocket(self) -> bool:
        """通过 WebSocket 连接"""
        logger.info(f"WebSocket MCP connection to {self.config.url} not yet implemented")
        return False

    def _send_jsonrpc(self, message: dict):
        """发送 JSON-RPC 消息"""
        if self._process and self._process.stdin:
            content = json.dumps(message, ensure_ascii=False)
            self._process.stdin.write(content + "\n")
            self._process.stdin.flush()

    def _read_jsonrpc(self, timeout: float = 5.0) -> dict | None:
        """读取 JSON-RPC 消息"""
        if self._process and self._process.stdout:
            import select

            if select.select([self._process.stdout], [], [], timeout)[0]:
                line = self._process.stdout.readline()
                if line:
                    return json.loads(line.decode("utf-8"))
        return None

    def _discover_tools(self):
        """发现 MCP 服务器提供的工具"""
        list_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        self._send_jsonrpc(list_request)
        response = self._read_jsonrpc()

        if response and response.get("result"):
            tools = response["result"].get("tools", [])
            for tool in tools:
                self._tools[tool["name"]] = McpToolDefinition(
                    name=tool["name"],
                    description=tool.get("description", ""),
                    input_schema=tool.get("inputSchema", {}),
                    server_name=self.config.name,
                )

        logger.info(f"Discovered {len(self._tools)} tools from {self.config.name}")

    def disconnect(self):
        """断开连接"""
        with self._lock:
            if self._process:
                self._process.terminate()
                self._process.wait(timeout=5)
                self._process = None
            self._connected = False
            self._tools.clear()

    def list_tools(self) -> list[McpToolDefinition]:
        """列出所有可用工具"""
        return list(self._tools.values())

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> tuple[bool, Any]:
        """
        调用工具

        Returns:
            Tuple[bool, Any]: (success, result_or_error)
        """
        if not self._connected:
            return False, "Not connected"

        if tool_name not in self._tools:
            return False, f"Unknown tool: {tool_name}"

        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }

        self._send_jsonrpc(request)
        response = self._read_jsonrpc(timeout=60)

        if response and response.get("result"):
            content = response["result"].get("content", [])
            if content and isinstance(content, list):
                return True, content[0].get("text", "")
            return True, ""

        if response and response.get("error"):
            return False, response["error"]

        return False, "No response from MCP server"


class McpServerManager:
    """
    MCP 服务器管理器

    管理多个 MCP 服务器连接。
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._clients: dict[str, McpClient] = {}
            cls._instance._tools: dict[str, McpToolDefinition] = {}
            cls._instance._initialized = False
        return cls._instance

    def load_config(self, config_path: Path = None) -> list[McpServerConfig]:
        """加载 MCP 配置"""
        if config_path is None:
            config_path = MCP_CONFIG_DIR / "config.json"

        if not config_path.exists():
            return []

        try:
            with open(config_path, encoding="utf-8") as f:
                config_data = json.load(f)

            servers = []
            for name, cfg in config_data.items():
                server = McpServerConfig(
                    name=name,
                    command=cfg.get("command", ""),
                    args=cfg.get("args", []),
                    env=cfg.get("env", {}),
                    transport=McpTransport(cfg.get("transport", "stdio")),
                    url=cfg.get("url", ""),
                    headers=cfg.get("headers", {}),
                )
                servers.append(server)

            return servers

        except Exception as e:
            logger.error(f"Failed to load MCP config: {e}")
            return []

    def save_config(self, servers: list[McpServerConfig], config_path: Path = None):
        """保存 MCP 配置"""
        if config_path is None:
            config_path = MCP_CONFIG_DIR / "config.json"

        config_path.parent.mkdir(parents=True, exist_ok=True)

        config_data = {}
        for server in servers:
            config_data[server.name] = {
                "command": server.command,
                "args": server.args,
                "env": server.env,
                "transport": server.transport.value,
                "url": server.url,
                "headers": server.headers,
            }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)

    def connect_server(self, config: McpServerConfig) -> bool:
        """连接 MCP 服务器"""
        if config.name in self._clients:
            return self._clients[config.name].connect()

        client = McpClient(config)
        if client.connect():
            self._clients[config.name] = client
            for tool in client.list_tools():
                self._tools[tool.name] = tool
            return True
        return False

    def disconnect_server(self, server_name: str):
        """断开 MCP 服务器"""
        if server_name in self._clients:
            self._clients[server_name].disconnect()
            del self._clients[server_name]

            for tool_name in list(self._tools.keys()):
                if self._tools[tool_name].server_name == server_name:
                    del self._tools[tool_name]

    def connect_all(self, config_path: Path = None) -> int:
        """连接所有配置的 MCP 服务器"""
        servers = self.load_config(config_path)
        connected = 0

        for server in servers:
            if self.connect_server(server):
                connected += 1

        self._initialized = True
        return connected

    def disconnect_all(self):
        """断开所有 MCP 服务器"""
        for server_name in list(self._clients.keys()):
            self.disconnect_server(server_name)

    def list_tools(self) -> list[McpToolDefinition]:
        """列出所有可用工具"""
        return list(self._tools.values())

    def get_tool(self, tool_name: str) -> McpToolDefinition | None:
        """获取工具定义"""
        return self._tools.get(tool_name)

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> tuple[bool, Any]:
        """调用工具"""
        tool = self._tools.get(tool_name)
        if not tool:
            return False, f"Unknown tool: {tool_name}"

        client = self._clients.get(tool.server_name)
        if not client:
            return False, f"Server not connected: {tool.server_name}"

        return client.call_tool(tool_name, arguments)

    def get_server_status(self) -> dict[str, Any]:
        """获取服务器状态"""
        return {
            server_name: {
                "connected": client._connected,
                "tool_count": len(client._tools),
            }
            for server_name, client in self._clients.items()
        }


_global_manager: McpServerManager | None = None


def get_mcp_manager() -> McpServerManager:
    """获取全局 MCP 管理器"""
    global _global_manager
    if _global_manager is None:
        _global_manager = McpServerManager()
    return _global_manager


def discover_mcp_tools(timeout: float = 120.0) -> list[McpToolDefinition]:
    """
    发现并加载 MCP 工具

    Returns:
        List[McpToolDefinition]: 工具列表
    """
    manager = get_mcp_manager()
    if not manager._initialized:
        manager.connect_all()

    tools = manager.list_tools()

    for tool in tools:
        from .tools.registry import registry

        registry.register(
            name=f"mcp_{tool.name}",
            toolset="mcp",
            schema={
                "name": f"mcp_{tool.name}",
                "description": f"[MCP:{tool.server_name}] {tool.description}",
                "parameters": tool.input_schema,
            },
            handler=lambda args, t=tool: _mcp_tool_handler(t, args),
            description=f"MCP tool from {tool.server_name}",
            emoji="🔌",
        )

    return tools


def _mcp_tool_handler(tool: McpToolDefinition, args: dict) -> str:
    """MCP 工具处理器"""
    manager = get_mcp_manager()
    success, result = manager.call_tool(tool.name, args)

    if success:
        return json.dumps({"success": True, "result": result}, ensure_ascii=False)
    else:
        return json.dumps({"success": False, "error": result}, ensure_ascii=False)


def setup_mcp_config():
    """设置 MCP 配置目录和示例配置"""
    MCP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    example_config = {
        "example-server": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
            "env": {},
            "transport": "stdio",
        }
    }

    example_path = MCP_CONFIG_DIR / "config.json.example"
    with open(example_path, "w", encoding="utf-8") as f:
        json.dump(example_config, f, ensure_ascii=False, indent=2)

    logger.info(f"Example MCP config created at {example_path}")
