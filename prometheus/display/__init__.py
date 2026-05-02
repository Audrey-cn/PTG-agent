"""
Prometheus Display System
包含 banner、logo、tool display 和命令注册表
"""

from prometheus.display.banner import (
    build_welcome_banner,
    get_commands_by_category,
)

from prometheus.display.tool_display import (
    KawaiiSpinner,
    build_tool_preview,
    get_tool_emoji,
    get_cute_tool_message,
    format_thinking_message,
    format_status_message,
)
