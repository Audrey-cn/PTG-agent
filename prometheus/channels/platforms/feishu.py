"""
飞书 Adapter 占位
"""
from typing import Optional, Any, Dict
from dataclasses import dataclass
from datetime import datetime

from . import PlatformAdapter


class FeishuAdapter(PlatformAdapter):
    platform_type = "feishu"
    platform_name = "飞书"
    required_dependencies = []

    def __init__(self, config):
        super().__init__(config)
        self.app_id = self.config.settings.get("app_id", "")
        self.app_secret = self.config.settings.get("app_secret", "")
        self.verification_token = self.config.settings.get("verification_token", "")

    def send(self, message: str, **kwargs) -> bool:
        print(f"[飞书] 发送占位: {message[:50]}...")
        return False

    def receive(self, timeout: float = 30, **kwargs) -> Optional[Any]:
        print("[飞书] 接收占位")
        return None

    def start(self) -> bool:
        print(f"[飞书] 适配器启动（占位），配置 app_id: {self.app_id}...")
        if not self._check_dependencies():
            return False
        if not self.app_id or not self.app_secret:
            print(f"⚠️ 飞书需要配置 app_id 和 app_secret")
            return False
        self._is_running = True
        return True

    def stop(self) -> bool:
        print("[飞书] 适配器停止")
        self._is_running = False
        return True
