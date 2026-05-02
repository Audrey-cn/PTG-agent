"""Backward-compat shim: re-export from security.registry."""

from prometheus.tools.security.registry import (  # noqa: F401
    ToolDefinition,
    ToolRegistry,
    ToolSchema,
    registry,
    tool_error,
    tool_result,
)


def discover_builtin_tools():
    """向后兼容别名：调用 load_all_tools 加载所有内置工具。"""
    from prometheus.tools import load_all_tools

    load_all_tools()
