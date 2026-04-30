"""
钉钉 Adapter 占位
"""
from typing import Optional, Any, Dict
from dataclasses import dataclass
from datetime import datetime

from . import PlatformAdapter


class DingtalkAdapter(PlatformAdapter):
    platform_type = "dingtalk"
    platform_name = "钉钉"
    required_dependencies = []

    def __init__(self, config):
        super().__init__(config)
        self.app_key = self.config.settings.get("app_key", "")
        self.app_secret = self.config.settings.get("app_secret", "")

    def send(self, message: str, **kwargs) -> bool:
        print(f"[钉钉] 发送占位: {message[:50]}...")
        return False

    def receive(self, timeout: float = 30, **kwargs) -> Optional[Any]:
        print("[钉钉] 接收占位")
        return None

    def start(self) -> bool:
        print(f"[钉钉] 适配器启动（占位），配置 app_key: {self.app_key}...")
        if not self._check_dependencies():
            return False
        if not self.app_key or not self.app_secret:
            print(f"⚠️ 钉钉需要配置 app_key 和 app_secret")
            return False
        self._is_running = True
        return True

    def stop(self) -> bool:
        print("[钉钉] 适配器停止")
        self._is_running = False
        return True
