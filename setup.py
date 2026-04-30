
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
    python_requires="&gt;=3.11",
    install_requires=[
        "openai&gt;=2.21.0,&lt;3",
        "anthropic&gt;=0.39.0,&lt;1",
        "python-dotenv&gt;=1.2.1,&lt;2",
        "fire&gt;=0.7.1,&lt;1",
        "httpx[socks]&gt;=0.28.1,&lt;1",
        "rich&gt;=14.3.3,&lt;15",
        "tenacity&gt;=9.1.4,&lt;10",
        "pyyaml&gt;=6.0.2,&lt;7",
        "requests&gt;=2.33.0,&lt;3",
        "jinja2&gt;=3.1.5,&lt;4",
        "pydantic&gt;=2.12.5,&lt;3",
        "prompt_toolkit&gt;=3.0.52,&lt;4",
        "numpy&gt;=1.24.0,&lt;3",
    ],
    extras_require={
        "dev": ["debugpy&gt;=1.8.0,&lt;2", "pytest&gt;=9.0.2,&lt;10", "pytest-asyncio&gt;=1.3.0,&lt;2", "ruff"],
        "mcp": ["mcp&gt;=1.2.0,&lt;2"],
        "web": ["fastapi&gt;=0.104.0,&lt;1", "uvicorn[standard]&gt;=0.24.0,&lt;1"],
        "file_watch": ["watchdog&gt;=4.0.0,&lt;5"],
        "messaging": ["python-telegram-bot[webhooks]&gt;=22.6,&lt;23", "discord.py[voice]&gt;=2.7.1,&lt;3", "aiohttp&gt;=3.13.3,&lt;4", "slack-bolt&gt;=1.18.0,&lt;2", "slack-sdk&gt;=3.27.0,&lt;4"],
        "cron": ["croniter&gt;=6.0.0,&lt;7"],
        "dingtalk": ["dingtalk-stream&gt;=0.20,&lt;1", "alibabacloud-dingtalk&gt;=2.0.0"],
        "feishu": ["lark-oapi&gt;=1.5.3,&lt;2"],
        "termux": [
            "python-telegram-bot[webhooks]&gt;=22.6,&lt;23",
            "croniter&gt;=6.0.0,&lt;7",
            "mcp&gt;=1.2.0,&lt;2",
        ],
    },
    entry_points={
        "console_scripts": [
            "ptg = prometheus.cli.main:main",
            "prometheus = prometheus.cli.main:main",
        ],
    },
)

