"""
Prometheus 工具模块
统一导出所有工具
"""

# 核心工具
from .terminal import handle_terminal, check_terminal_requirements
from .file import (
    handle_read_file,
    handle_write_file,
    handle_patch,
    handle_search_files,
    handle_list_directory
)

# 扩展工具
from .browser import (
    handle_navigate,
    handle_get_content,
    handle_click,
    handle_type_text,
    handle_screenshot,
    handle_wait,
    handle_close,
    check_browser_requirements
)

from .mcp import (
    handle_list_servers,
    handle_add_server,
    handle_remove_server,
    check_mcp_requirements
)

from .vision import (
    handle_analyze_image,
    check_vision_requirements
)

from .cron import (
    handle_add_job,
    handle_remove_job,
    handle_list_jobs,
    check_cron_requirements
)

# 注册表
from .registry import registry, get_registry, tool_result, tool_error

__all__ = [
    # 注册表
    "registry",
    "get_registry",
    "tool_result",
    "tool_error",
    
    # 核心工具
    "handle_terminal",
    "check_terminal_requirements",
    "handle_read_file",
    "handle_write_file",
    "handle_patch",
    "handle_search_files",
    "handle_list_directory",
    
    # 浏览器
    "handle_navigate",
    "handle_get_content",
    "handle_click",
    "handle_type_text",
    "handle_screenshot",
    "handle_wait",
    "handle_close",
    "check_browser_requirements",
    
    # MCP
    "handle_list_servers",
    "handle_add_server",
    "handle_remove_server",
    "check_mcp_requirements",
    
    # 视觉
    "handle_analyze_image",
    "check_vision_requirements",
    
    # 定时
    "handle_add_job",
    "handle_remove_job",
    "handle_list_jobs",
    "check_cron_requirements",
]


def load_all_tools():
    """加载所有工具（触发注册）"""
    import prometheus.tools.terminal
    import prometheus.tools.file
    import prometheus.tools.browser
    import prometheus.tools.mcp
    import prometheus.tools.vision
    import prometheus.tools.cron
