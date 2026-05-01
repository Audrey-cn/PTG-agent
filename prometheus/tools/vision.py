"""
Prometheus 视觉分析工具
使用视觉模型分析图片
"""

import base64
import os
from pathlib import Path
from typing import Any

from .registry import tool_error, tool_result

# 尝试导入视觉相关库
try:
    import anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


def load_image_base64(path: str) -> str:
    """加载图片为 base64"""
    expanded = Path(path).expanduser()

    if not expanded.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    with open(expanded, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def analyze_image(image_path: str, prompt: str = "描述这张图片") -> dict[str, Any]:
    """
    分析图片内容

    Args:
        image_path: 图片路径
        prompt: 分析提示词

    Returns:
        包含 analysis 的字典
    """
    try:
        # 检查 API 密钥
        api_key = None

        if ANTHROPIC_AVAILABLE:
            api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

        if OPENAI_AVAILABLE:
            api_key = api_key or os.getenv("OPENAI_API_KEY")

        if not api_key:
            return {"error": "未找到视觉分析 API 密钥，请配置 ANTHROPIC_API_KEY 或 OPENAI_API_KEY"}

        # 加载图片
        image_data = load_image_base64(image_path)

        # 根据可用 API 调用
        if ANTHROPIC_AVAILABLE and os.getenv("ANTHROPIC_API_KEY"):
            return analyze_with_anthropic(image_data, prompt)
        elif OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
            return analyze_with_openai(image_data, prompt)
        else:
            return {"error": "无可用的视觉分析 API"}

    except FileNotFoundError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"分析失败: {str(e)}"}


def analyze_with_anthropic(image_data: str, prompt: str) -> dict[str, Any]:
    """使用 Anthropic API 分析"""
    try:
        client = anthropic.Anthropic()

        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_data,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )

        return {"analysis": response.content[0].text, "model": "claude-3-5-sonnet"}

    except Exception as e:
        return {"error": f"Anthropic API 错误: {str(e)}"}


def analyze_with_openai(image_data: str, prompt: str) -> dict[str, Any]:
    """使用 OpenAI API 分析"""
    try:
        client = OpenAI()

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_data}"},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            max_tokens=1024,
        )

        return {"analysis": response.choices[0].message.content, "model": "gpt-4o"}

    except Exception as e:
        return {"error": f"OpenAI API 错误: {str(e)}"}


# 视觉工具 schemas
ANALYZE_IMAGE_SCHEMA = {
    "name": "analyze_image",
    "description": "使用视觉模型分析图片内容",
    "parameters": {
        "type": "object",
        "properties": {
            "image_path": {"type": "string", "description": "图片路径"},
            "prompt": {"type": "string", "description": "分析提示词", "default": "描述这张图片"},
        },
        "required": ["image_path"],
    },
}


def check_vision_requirements() -> bool:
    """检查视觉工具需求"""
    return (ANTHROPIC_AVAILABLE and os.getenv("ANTHROPIC_API_KEY")) or (
        OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY")
    )


def handle_analyze_image(args: dict[str, Any], **kwargs) -> str:
    image_path = args.get("image_path", "")
    prompt = args.get("prompt", "描述这张图片")

    result = analyze_image(image_path, prompt)

    if "error" in result:
        return tool_error(result["error"])

    return tool_result(result)


# 注册工具
from .registry import registry

registry.register(
    name="analyze_image",
    toolset="vision",
    schema=ANALYZE_IMAGE_SCHEMA,
    handler=handle_analyze_image,
    description="分析图片内容",
    emoji="👁️",
    check_fn=check_vision_requirements,
)
