"""
Prometheus 终端工具
执行 shell 命令
"""

import os
import subprocess
from typing import Any

from .registry import tool_error, tool_result


def execute_command(command: str, timeout: int = 60, workdir: str | None = None) -> dict[str, Any]:
    """
    执行 shell 命令

    Args:
        command: 要执行的命令
        timeout: 超时时间（秒），默认 60
        workdir: 工作目录

    Returns:
        包含 output, exit_code, error 的字典
    """
    try:
        # 验证命令
        if not command or not isinstance(command, str):
            return {"error": "命令不能为空"}

        # 设置工作目录
        cwd = workdir if workdir else os.getcwd()

        # 执行命令
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )

        return {
            "output": result.stdout,
            "error": result.stderr if result.stderr else None,
            "exit_code": result.returncode,
        }

    except subprocess.TimeoutExpired:
        return {"output": "", "error": f"命令执行超时（{timeout}秒）", "exit_code": -1}
    except Exception as e:
        return {"output": "", "error": f"执行失败: {str(e)}", "exit_code": -1}


def check_terminal_requirements() -> bool:
    """检查终端工具需求"""
    return True  # 基础版无需额外依赖


# 工具 schema
TERMINAL_SCHEMA = {
    "name": "terminal",
    "description": "在本地终端执行 shell 命令。用于运行脚本、安装包、执行程序等。",
    "parameters": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的 shell 命令"},
            "timeout": {
                "type": "integer",
                "description": "超时时间（秒），默认 60",
                "default": 60,
                "minimum": 1,
                "maximum": 3600,
            },
            "workdir": {"type": "string", "description": "工作目录（可选）"},
        },
        "required": ["command"],
    },
}


def handle_terminal(args: dict[str, Any], **kwargs) -> str:
    """处理终端命令"""
    command = args.get("command", "")
    timeout = args.get("timeout", 60)
    workdir = args.get("workdir")

    result = execute_command(command, timeout, workdir)

    if result.get("error") and not result.get("output"):
        return tool_error(result["error"])

    return tool_result(result)


# 注册工具
from .registry import registry

registry.register(
    name="terminal",
    toolset="core",
    schema=TERMINAL_SCHEMA,
    handler=handle_terminal,
    description="执行 shell 命令",
    emoji="💻",
    check_fn=check_terminal_requirements,
    max_result_size=50000,
)
