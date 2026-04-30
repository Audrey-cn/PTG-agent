"""
Discord Adapter 占位
"""
from typing import Optional, Any, Dict
from dataclasses import dataclass
from datetime import datetime

from . import PlatformAdapter


class DiscordAdapter(PlatformAdapter):
    platform_type = "discord"
    platform_name = "Discord"
    required_dependencies = ["discord"]

    def __init__(self, config):
        super().__init__(config)
        self.token = self.config.settings.get("token", "")
        self.allowed_channel_ids = self.config.settings.get("allowed_channel_ids", [])

    def send(self, message: str, **kwargs) -> bool:
        print(f"[Discord] 发送占位: {message[:50]}...")
        return False

    def receive(self, timeout: float = 30, **kwargs) -> Optional[Any]:
        print("[Discord] 接收占位")
        return None

    def start(self) -> bool:
        print(f"[Discord] 适配器启动（占位），配置 token: {self.token[:20]}...")
        if not self._check_dependencies():
            return False
        if not self.token:
            print(f"⚠️ Discord 需要配置 token")
            return False
        self._is_running = True
        return True

    def stop(self) -> bool:
        print("[Discord] 适配器停止")
        self._is_running = False
        return True
