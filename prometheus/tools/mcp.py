"""
Prometheus MCP (Model Context Protocol) 集成工具
支持调用 MCP 服务器和工具
"""
import json
import subprocess
from typing import Optional, Dict, Any, List
from pathlib import Path
from .registry import tool_result, tool_error

# 尝试导入 MCP SDK
try:
    from mcp import ClientSession
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


class MCPManager:
    """MCP 管理器"""
    
    def __init__(self):
        self.servers: Dict[str, Any] = {}
        self.config_path = Path.home() / ".prometheus" / "mcp.json"
    
    def load_config(self) -> List[Dict[str, Any]]:
        """加载 MCP 配置"""
        if not self.config_path.exists():
            return []
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get("servers", [])
        except Exception:
            return []
    
    def save_config(self, servers: List[Dict[str, Any]]):
        """保存 MCP 配置"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump({"servers": servers}, f, indent=2)
    
    def list_servers(self) -> List[Dict[str, str]]:
        """列出已配置的服务器"""
        servers = self.load_config()
        return [
            {"name": s.get("name", "?"), "command": s.get("command", "")}
            for s in servers
        ]


def list_mcp_servers() -> Dict[str, Any]:
    """
    列出已配置的 MCP 服务器
    
    Returns:
        包含 servers 的字典
    """
    try:
        manager = MCPManager()
        servers = manager.list_servers()
        
        return {
            "servers": servers,
            "count": len(servers)
        }
    
    except Exception as e:
        return {"error": f"列出服务器失败: {str(e)}"}


def add_server(name: str, command: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    添加 MCP 服务器
    
    Args:
        name: 服务器名称
        command: 启动命令
        args: 启动参数
    
    Returns:
        包含 success 的字典
    """
    try:
        manager = MCPManager()
        servers = manager.load_config()
        
        # 检查是否已存在
        for s in servers:
            if s.get("name") == name:
                return {"error": f"服务器 {name} 已存在"}
        
        # 添加新服务器
        servers.append({
            "name": name,
            "command": command,
            "args": args or []
        })
        
        manager.save_config(servers)
        
        return {
            "success": True,
            "name": name,
            "command": command
        }
    
    except Exception as e:
        return {"error": f"添加服务器失败: {str(e)}"}


def remove_server(name: str) -> Dict[str, Any]:
    """
    移除 MCP 服务器
    
    Args:
        name: 服务器名称
    
    Returns:
        包含 success 的字典
    """
    try:
        manager = MCPManager()
        servers = manager.load_config()
        
        # 过滤掉指定的服务器
        servers = [s for s in servers if s.get("name") != name]
        
        manager.save_config(servers)
        
        return {
            "success": True,
            "name": name
        }
    
    except Exception as e:
        return {"error": f"移除服务器失败: {str(e)}"}


# MCP 工具 schemas
LIST_SERVERS_SCHEMA = {
    "name": "list_mcp_servers",
    "description": "列出已配置的 MCP 服务器",
    "parameters": {
        "type": "object",
        "properties": {}
    }
}

ADD_SERVER_SCHEMA = {
    "name": "add_mcp_server",
    "description": "添加 MCP 服务器配置",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "服务器名称"},
            "command": {"type": "string", "description": "启动命令"},
            "args": {"type": "array", "description": "启动参数", "items": {"type": "string"}}
        },
        "required": ["name", "command"]
    }
}

REMOVE_SERVER_SCHEMA = {
    "name": "remove_mcp_server",
    "description": "移除 MCP 服务器配置",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "服务器名称"}
        },
        "required": ["name"]
    }
}


def check_mcp_requirements() -> bool:
    """检查 MCP 需求"""
    return MCP_AVAILABLE


def handle_list_servers(args: Dict[str, Any], **kwargs) -> str:
    result = list_mcp_servers()
    
    if "error" in result:
        return tool_error(result["error"])
    
    return tool_result(result)


def handle_add_server(args: Dict[str, Any], **kwargs) -> str:
    name = args.get("name", "")
    command = args.get("command", "")
    args_list = args.get("args", [])
    
    result = add_server(name, command, args_list)
    
    if "error" in result:
        return tool_error(result["error"])
    
    return tool_result(result)


def handle_remove_server(args: Dict[str, Any], **kwargs) -> str:
    name = args.get("name", "")
    
    result = remove_server(name)
    
    if "error" in result:
        return tool_error(result["error"])
    
    return tool_result(result)


# 注册工具
from .registry import registry

registry.register(
    name="list_mcp_servers",
    toolset="mcp",
    schema=LIST_SERVERS_SCHEMA,
    handler=handle_list_servers,
    description="列出 MCP 服务器",
    emoji="🔌"
)

registry.register(
    name="add_mcp_server",
    toolset="mcp",
    schema=ADD_SERVER_SCHEMA,
    handler=handle_add_server,
    description="添加 MCP 服务器",
    emoji="➕"
)

registry.register(
    name="remove_mcp_server",
    toolset="mcp",
    schema=REMOVE_SERVER_SCHEMA,
    handler=handle_remove_server,
    description="移除 MCP 服务器",
    emoji="➖"
)
