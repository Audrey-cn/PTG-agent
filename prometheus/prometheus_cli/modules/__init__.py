"""
CLI 模块包 - 将大型 main.py 拆分为功能聚焦的模块

这些模块保持与原有 main.py 相同的接口，但结构更清晰
"""

from . import (
    argument_parsers,
    chat_commands,
    gateway_commands,
    setup_commands,
    utility_functions
)

__all__ = [
    'argument_parsers',
    'chat_commands', 
    'gateway_commands',
    'setup_commands',
    'utility_functions'
]