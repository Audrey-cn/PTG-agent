"""
Prometheus CLI 包

提供命令行界面功能：
- 命令解析和执行
- 各种子命令处理
"""

from .main import (
    cmd_setup,
    cmd_doctor,
    cmd_model,
    cmd_config,
    cmd_status,
    cmd_seed,
    cmd_gene,
    cmd_memory,
    cmd_kb,
    cmd_dict,
    cmd_update,
    build_parser,
    main,
)

__all__ = [
    "cmd_setup",
    "cmd_doctor",
    "cmd_model",
    "cmd_config",
    "cmd_status",
    "cmd_seed",
    "cmd_gene",
    "cmd_memory",
    "cmd_kb",
    "cmd_dict",
    "cmd_update",
    "build_parser",
    "main",
]
