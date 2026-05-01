"""全局状态管理 - GlobalState."""

from __future__ import annotations

import threading
from typing import Any


class GlobalState:
    """Prometheus 全局状态管理器"""

    _instance: GlobalState | None = None
    _lock = threading.Lock()

    def __init__(self):
        self._orchestrator: Any | None = None
        self._steer_manager: Any | None = None
        self._discoverer: Any | None = None
        self._webhook_tool: Any | None = None
        self._initialized = False
        self._init_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> GlobalState:
        """获取全局单例实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def initialize(self):
        """延迟初始化所有组件"""
        if self._initialized:
            return

        with self._init_lock:
            if self._initialized:
                return

            from prometheus.cli.dynamic_models import get_discoverer
            from prometheus.cli.steer import get_steer_manager
            from prometheus.orchestrator import get_orchestrator
            from prometheus.tools.webhook_tool import get_webhook_tool

            self._orchestrator = get_orchestrator()
            self._steer_manager = get_steer_manager()
            self._discoverer = get_discoverer()
            self._webhook_tool = get_webhook_tool()

            self._initialized = True

    @property
    def orchestrator(self) -> Any:
        """获取编排器实例"""
        if self._orchestrator is None:
            self.initialize()
        return self._orchestrator

    @property
    def steer_manager(self) -> Any:
        """获取转向管理器实例"""
        if self._steer_manager is None:
            self.initialize()
        return self._steer_manager

    @property
    def discoverer(self) -> Any:
        """获取模型发现器实例"""
        if self._discoverer is None:
            self.initialize()
        return self._discoverer

    @property
    def webhook_tool(self) -> Any:
        """获取 Webhook 工具实例"""
        if self._webhook_tool is None:
            self.initialize()
        return self._webhook_tool

    def reset(self):
        """重置全局状态（主要用于测试）"""
        with self._lock:
            self._orchestrator = None
            self._steer_manager = None
            self._discoverer = None
            self._webhook_tool = None
            self._initialized = False


_state: GlobalState | None = None


def get_state() -> GlobalState:
    """获取全局状态管理器"""
    global _state
    if _state is None:
        _state = GlobalState.get_instance()
    return _state
