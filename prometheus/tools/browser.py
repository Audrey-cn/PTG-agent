"""
Prometheus 浏览器控制工具
使用 Playwright 控制浏览器
"""

from typing import Any

from .registry import tool_error, tool_result

# 尝试导入 Playwright
try:
    from playwright.sync_api import Page, sync_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Page = None


class BrowserController:
    """浏览器控制器"""

    _playwright = None
    _browser = None
    _page = None

    @classmethod
    def get_browser(cls, headless: bool = True):
        """获取或创建浏览器实例"""
        if cls._browser is None or cls._browser.is_closed():
            if not PLAYWRIGHT_AVAILABLE:
                raise ImportError(
                    "Playwright 未安装，请运行: pip install playwright && playwright install"
                )

            cls._playwright = sync_playwright().start()
            cls._browser = cls._playwright.chromium.launch(headless=headless)
            cls._page = cls._browser.new_page()

        return cls._browser, cls._page

    @classmethod
    def close(cls):
        """关闭浏览器"""
        if cls._browser:
            cls._browser.close()
            cls._browser = None
        if cls._playwright:
            cls._playwright.stop()
            cls._playwright = None
        cls._page = None


def navigate(url: str, headless: bool = True) -> dict[str, Any]:
    """
    导航到 URL

    Args:
        url: 目标 URL
        headless: 是否无头模式

    Returns:
        包含 title, url 的字典
    """
    try:
        if not PLAYWRIGHT_AVAILABLE:
            return {
                "error": "Playwright 未安装，请运行: pip install playwright && playwright install"
            }

        browser, page = BrowserController.get_browser(headless)
        page.goto(url, wait_until="domcontentloaded")

        return {"success": True, "title": page.title(), "url": page.url}

    except Exception as e:
        return {"error": f"导航失败: {str(e)}"}


def get_page_content() -> dict[str, Any]:
    """
    获取页面内容

    Returns:
        包含 content, title, url 的字典
    """
    try:
        if not PLAYWRIGHT_AVAILABLE:
            return {"error": "Playwright 未安装"}

        _, page = BrowserController.get_browser()

        return {"content": page.content(), "title": page.title(), "url": page.url}

    except Exception as e:
        return {"error": f"获取内容失败: {str(e)}"}


def click(selector: str) -> dict[str, Any]:
    """
    点击元素

    Args:
        selector: CSS 选择器

    Returns:
        包含 success 的字典
    """
    try:
        if not PLAYWRIGHT_AVAILABLE:
            return {"error": "Playwright 未安装"}

        _, page = BrowserController.get_browser()
        page.click(selector)

        return {"success": True}

    except Exception as e:
        return {"error": f"点击失败: {str(e)}"}


def type_text(selector: str, text: str) -> dict[str, Any]:
    """
    输入文本

    Args:
        selector: CSS 选择器
        text: 要输入的文本

    Returns:
        包含 success 的字典
    """
    try:
        if not PLAYWRIGHT_AVAILABLE:
            return {"error": "Playwright 未安装"}

        _, page = BrowserController.get_browser()
        page.fill(selector, text)

        return {"success": True}

    except Exception as e:
        return {"error": f"输入失败: {str(e)}"}


def take_screenshot(path: str | None = None) -> dict[str, Any]:
    """
    截图

    Args:
        path: 保存路径（可选）

    Returns:
        包含 path 的字典
    """
    try:
        if not PLAYWRIGHT_AVAILABLE:
            return {"error": "Playwright 未安装"}

        _, page = BrowserController.get_browser()

        if path:
            page.screenshot(path=path)
            return {"success": True, "path": path}
        else:
            screenshot_bytes = page.screenshot()
            return {"success": True, "screenshot": screenshot_bytes.hex()[:100] + "..."}

    except Exception as e:
        return {"error": f"截图失败: {str(e)}"}


def wait_for_selector(selector: str, timeout: int = 30000) -> dict[str, Any]:
    """
    等待元素出现

    Args:
        selector: CSS 选择器
        timeout: 超时时间（毫秒）

    Returns:
        包含 success 的字典
    """
    try:
        if not PLAYWRIGHT_AVAILABLE:
            return {"error": "Playwright 未安装"}

        _, page = BrowserController.get_browser()
        page.wait_for_selector(selector, timeout=timeout)

        return {"success": True}

    except Exception as e:
        return {"error": f"等待失败: {str(e)}"}


def close_browser() -> dict[str, Any]:
    """
    关闭浏览器

    Returns:
        包含 success 的字典
    """
    try:
        BrowserController.close()
        return {"success": True}
    except Exception as e:
        return {"error": f"关闭失败: {str(e)}"}


# 浏览器工具 schemas
NAVIGATE_SCHEMA = {
    "name": "navigate",
    "description": "导航到指定 URL",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "目标 URL"},
            "headless": {"type": "boolean", "description": "是否无头模式", "default": True},
        },
        "required": ["url"],
    },
}

GET_CONTENT_SCHEMA = {
    "name": "get_page_content",
    "description": "获取当前页面内容",
    "parameters": {"type": "object", "properties": {}},
}

CLICK_SCHEMA = {
    "name": "click",
    "description": "点击页面元素",
    "parameters": {
        "type": "object",
        "properties": {"selector": {"type": "string", "description": "CSS 选择器"}},
        "required": ["selector"],
    },
}

TYPE_SCHEMA = {
    "name": "type_text",
    "description": "在输入框中输入文本",
    "parameters": {
        "type": "object",
        "properties": {
            "selector": {"type": "string", "description": "CSS 选择器"},
            "text": {"type": "string", "description": "要输入的文本"},
        },
        "required": ["selector", "text"],
    },
}

SCREENSHOT_SCHEMA = {
    "name": "screenshot",
    "description": "截取当前页面",
    "parameters": {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "保存路径（可选）"}},
    },
}

WAIT_SCHEMA = {
    "name": "wait_for_selector",
    "description": "等待元素出现",
    "parameters": {
        "type": "object",
        "properties": {
            "selector": {"type": "string", "description": "CSS 选择器"},
            "timeout": {"type": "integer", "description": "超时时间（毫秒）", "default": 30000},
        },
        "required": ["selector"],
    },
}

CLOSE_SCHEMA = {
    "name": "close_browser",
    "description": "关闭浏览器",
    "parameters": {"type": "object", "properties": {}},
}


def check_browser_requirements() -> bool:
    """检查浏览器工具需求"""
    return PLAYWRIGHT_AVAILABLE


def handle_navigate(args: dict[str, Any], **kwargs) -> str:
    url = args.get("url", "")
    headless = args.get("headless", True)

    result = navigate(url, headless)

    if "error" in result:
        return tool_error(result["error"])

    return tool_result(result)


def handle_get_content(args: dict[str, Any], **kwargs) -> str:
    result = get_page_content()

    if "error" in result:
        return tool_error(result["error"])

    return tool_result(result)


def handle_click(args: dict[str, Any], **kwargs) -> str:
    selector = args.get("selector", "")

    result = click(selector)

    if "error" in result:
        return tool_error(result["error"])

    return tool_result(result)


def handle_type_text(args: dict[str, Any], **kwargs) -> str:
    selector = args.get("selector", "")
    text = args.get("text", "")

    result = type_text(selector, text)

    if "error" in result:
        return tool_error(result["error"])

    return tool_result(result)


def handle_screenshot(args: dict[str, Any], **kwargs) -> str:
    path = args.get("path")

    result = take_screenshot(path)

    if "error" in result:
        return tool_error(result["error"])

    return tool_result(result)


def handle_wait(args: dict[str, Any], **kwargs) -> str:
    selector = args.get("selector", "")
    timeout = args.get("timeout", 30000)

    result = wait_for_selector(selector, timeout)

    if "error" in result:
        return tool_error(result["error"])

    return tool_result(result)


def handle_close(args: dict[str, Any], **kwargs) -> str:
    result = close_browser()

    if "error" in result:
        return tool_error(result["error"])

    return tool_result(result)


# 注册工具
from .registry import registry

registry.register(
    name="navigate",
    toolset="browser",
    schema=NAVIGATE_SCHEMA,
    handler=handle_navigate,
    description="导航到 URL",
    emoji="🌐",
    check_fn=check_browser_requirements,
)

registry.register(
    name="get_page_content",
    toolset="browser",
    schema=GET_CONTENT_SCHEMA,
    handler=handle_get_content,
    description="获取页面内容",
    emoji="📄",
    check_fn=check_browser_requirements,
)

registry.register(
    name="click",
    toolset="browser",
    schema=CLICK_SCHEMA,
    handler=handle_click,
    description="点击页面元素",
    emoji="🖱️",
    check_fn=check_browser_requirements,
)

registry.register(
    name="type_text",
    toolset="browser",
    schema=TYPE_SCHEMA,
    handler=handle_type_text,
    description="输入文本",
    emoji="⌨️",
    check_fn=check_browser_requirements,
)

registry.register(
    name="screenshot",
    toolset="browser",
    schema=SCREENSHOT_SCHEMA,
    handler=handle_screenshot,
    description="截图",
    emoji="📸",
    check_fn=check_browser_requirements,
)

registry.register(
    name="wait_for_selector",
    toolset="browser",
    schema=WAIT_SCHEMA,
    handler=handle_wait,
    description="等待元素",
    emoji="⏳",
    check_fn=check_browser_requirements,
)

registry.register(
    name="close_browser",
    toolset="browser",
    schema=CLOSE_SCHEMA,
    handler=handle_close,
    description="关闭浏览器",
    emoji="❌",
    check_fn=check_browser_requirements,
)
