
#!/usr/bin/env python3
"""
Prometheus 安装脚本 - 向后兼容旧版本 pip
"""

from setuptools import setup, find_packages
import pathlib

# 获取 README
here = pathlib.Path(__file__).parent.resolve()
long_description = (here / "README.md").read_text(encoding="utf-8")

setup(
    name="prometheus-ptg",
    version="0.8.0",
    description="Prometheus — Teach-To-Grow 种子基因编辑器，史诗编史官系统",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Audrey · 001X",
    packages=find_packages(include=["prometheus", "prometheus.*"]),
    python_requires=">=3.11",
    install_requires=[
        "openai>=2.21.0,<3",
        "anthropic>=0.39.0,<1",
        "python-dotenv>=1.2.1,<2",
        "fire>=0.7.1,<1",
        "httpx[socks]>=0.28.1,<1",
        "rich>=14.3.3,<15",
        "tenacity>=9.1.4,<10",
        "pyyaml>=6.0.2,<7",
        "requests>=2.33.0,<3",
        "jinja2>=3.1.5,<4",
        "pydantic>=2.12.5,<3",
        "prompt_toolkit>=3.0.52,<4",
        "numpy>=1.24.0,<3",
    ],
    extras_require={
        "dev": ["debugpy>=1.8.0,<2", "pytest>=9.0.2,<10", "pytest-asyncio>=1.3.0,<2", "ruff"],
        "mcp": ["mcp>=1.2.0,<2"],
        "web": ["fastapi>=0.104.0,<1", "uvicorn[standard]>=0.24.0,<1"],
        "file_watch": ["watchdog>=4.0.0,<5"],
        "messaging": ["python-telegram-bot[webhooks]>=22.6,<23", "discord.py[voice]>=2.7.1,<3", "aiohttp>=3.13.3,<4", "slack-bolt>=1.18.0,<2", "slack-sdk>=3.27.0,<4"],
        "cron": ["croniter>=6.0.0,<7"],
        "dingtalk": ["dingtalk-stream>=0.20,<1", "alibabacloud-dingtalk>=2.0.0"],
        "feishu": ["lark-oapi>=1.5.3,<2"],
        "termux": [
            "python-telegram-bot[webhooks]>=22.6,<23",
            "croniter>=6.0.0,<7",
            "mcp>=1.2.0,<2",
        ],
    },
    entry_points={
        "console_scripts": [
            "ptg = prometheus.cli.main:main",
            "prometheus = prometheus.cli.main:main",
        ],
    },
)

