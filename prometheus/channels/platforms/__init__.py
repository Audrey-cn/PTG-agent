"""
Prometheus 平台 Adapter 基础架构
参考 Hermes Gateway 设计

每个平台实现统一的接口
"""
from abc import ABC, abstractmethod
from typing import Optional, Any, Dict, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging

from prometheus.channels.base import Channel, ChannelConfig, ChannelMessage, ChannelResponse

logger = logging.getLogger(__name__)


class PlatformAdapter(Channel, ABC):
    """平台适配器基类（继承自 Channel）"""

    platform_type: str
    platform_name: str
    required_dependencies: List[str] = []

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.session = None
        self._session_id = None

    @abstractmethod
    def send(self, message: str, **kwargs) -> bool:
        """发送消息"""
        pass

    @abstractmethod
    def receive(self, timeout: float = 30, **kwargs) -> Optional[ChannelResponse]:
        """接收消息"""
        pass

    @abstractmethod
    def start(self) -> bool:
        """启动适配器"""
        pass

    @abstractmethod
    def stop(self) -> bool:
        """停止适配器"""
        pass

    def status(self) -> Dict[str, Any]:
        status = super().status()
        status["platform"] = self.platform_type
        status["session_id"] = self._session_id
        return status

    def _check_dependencies(self) -> bool:
        """检查依赖"""
        missing = []
        for dep in self.required_dependencies:
            try:
                __import__(dep)
            except ImportError:
                missing.append(dep)
        if missing:
            logger.warning(f"平台 {self.platform_name} 缺少依赖: {', '.join(missing)}")
            return False
        return True


# 导出各平台 Adapter
from .telegram import TelegramAdapter
from .discord import DiscordAdapter
from .feishu import FeishuAdapter
from .dingtalk import DingtalkAdapter

__all__ = [
    "PlatformAdapter",
    "TelegramAdapter",
    "DiscordAdapter",
    "FeishuAdapter",
    "DingtalkAdapter",
]

