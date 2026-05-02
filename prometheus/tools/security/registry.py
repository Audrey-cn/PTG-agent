"""
Prometheus 工具注册表
所有工具通过此模块注册和管理
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolSchema:
    """工具 schema 定义"""

    name: str
    description: str
    parameters: dict[str, Any]
    required: list[str] | None = None


@dataclass
class ToolDefinition:
    """工具定义"""

    name: str
    toolset: str
    schema: ToolSchema
    handler: Callable
    description: str = ""
    emoji: str = "🔧"
    check_fn: Callable | None = None
    max_result_size: int = 10000


class ToolRegistry:
    """工具注册表"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
            cls._instance._toolsets = {}
        return cls._instance

    def register(
        self,
        name: str,
        toolset: str,
        schema: dict[str, Any],
        handler: Callable[..., str],
        check_fn: Callable[[], tuple[bool, str]] | None = None,
        emoji: str = "",
        max_result_size_chars: float = float("inf"),
        **kwargs,
    ) -> None:
        """注册工具"""
        tool_def = ToolDefinition(
            name=name,
            toolset=toolset,
            schema=ToolSchema(
                name=schema.get("name", name),
                description=schema.get("description", ""),
                parameters=schema.get("parameters", {}),
                required=schema.get("required"),
            ),
            handler=handler,
            description=schema.get("description", ""),
            emoji=emoji,
            check_fn=check_fn,
            max_result_size=int(max_result_size_chars) if max_result_size_chars != float("inf") else 10000,
        )

        self._tools[name] = tool_def

        if toolset not in self._toolsets:
            self._toolsets[toolset] = []
        if name not in self._toolsets[toolset]:
            self._toolsets[toolset].append(name)

    def get(self, name: str) -> ToolDefinition | None:
        """获取工具定义"""
        return self._tools.get(name)

    def list_tools(self, toolset: str | None = None) -> list[str]:
        """列出工具"""
        if toolset:
            return self._toolsets.get(toolset, [])
        return list(self._tools.keys())

    def list_toolsets(self) -> list[str]:
        """列出工具集"""
        return list(self._toolsets.keys())

    def get_all_tool_names(self) -> list[str]:
        """获取所有工具名称列表"""
        return list(self._tools.keys())

    def get_all_schemas(self) -> list[dict[str, Any]]:
        """获取所有工具的 schema"""
        schemas = []
        for tool in self._tools.values():
            schema_dict = {
                "name": tool.schema.name,
                "description": tool.schema.description,
                "parameters": tool.schema.parameters,
            }
            if tool.schema.required:
                schema_dict["required"] = tool.schema.required
            schemas.append(schema_dict)
        return schemas

    def check_requirements(self) -> dict[str, bool]:
        """检查工具需求"""
        results = {}
        for name, tool in self._tools.items():
            if tool.check_fn:
                try:
                    results[name] = tool.check_fn()
                except Exception:
                    results[name] = False
            else:
                results[name] = True
        return results

    def call(self, name: str, args: dict[str, Any], **kwargs) -> str:
        """调用工具"""
        tool = self.get(name)
        if not tool:
            return json.dumps({"error": f"Tool not found: {name}"}, ensure_ascii=False)

        try:
            result = tool.handler(args, **kwargs)
            return result
        except Exception as e:
            return json.dumps(
                {"error": f"Tool execution failed: {str(e)}", "tool": name}, ensure_ascii=False
            )


# 全局单例
registry = ToolRegistry()


def tool_result(data: dict[str, Any]) -> str:
    """工具结果格式化"""
    return json.dumps(data, ensure_ascii=False, indent=2)


def tool_error(message: str, success: bool = False) -> str:
    """工具错误格式化"""
    return json.dumps({"error": message, "success": success}, ensure_ascii=False)


def get_registry() -> ToolRegistry:
    """获取工具注册表"""
    return registry
