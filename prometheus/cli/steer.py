"""🎯 /steer 命令 - 运行时纠偏."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass
class SteerMessage:
    """转向消息"""

    content: str
    timestamp: float
    applied: bool = False


class SteerManager:
    """转向管理器"""

    def __init__(self):
        self._pending_steer: str | None = None
        self._steer_lock = threading.Lock()
        self._steer_history: list[SteerMessage] = []

    def steer(self, message: str) -> bool:
        """注入转向消息

        Args:
            message: 要注入的提示内容

        Returns:
            True 如果成功，否则 False
        """
        if not message or not message.strip():
            return False

        with self._steer_lock:
            self._pending_steer = message.strip()
            self._steer_history.append(
                SteerMessage(
                    content=message.strip(),
                    timestamp=0.0,  # 时间戳可在需要时添加
                    applied=False,
                )
            )
        return True

    def consume_steer(self) -> str | None:
        """消费待处理的转向消息

        在工具调用完成后调用，获取并清除待处理的转向消息。

        Returns:
            转向消息内容，如果没有则返回 None
        """
        with self._steer_lock:
            if self._pending_steer is None:
                return None
            message = self._pending_steer
            self._pending_steer = None
            return message

    def peek_steer(self) -> str | None:
        """查看待处理的转向消息（不消费）"""
        with self._steer_lock:
            return self._pending_steer

    def clear_steer(self):
        """清除待处理的转向消息"""
        with self._steer_lock:
            self._pending_steer = None

    @property
    def has_pending_steer(self) -> bool:
        """是否有待处理的转向消息"""
        with self._steer_lock:
            return self._pending_steer is not None

    def get_history(self) -> list[SteerMessage]:
        """获取转向历史"""
        with self._steer_lock:
            return list(self._steer_history)


class PrometheusSteerMixin:
    """普罗米修斯转向混入

    可以被添加到 PrometheusAgentLoop 或其他 Agent 类中，
    提供 /steer 功能。
    """

    def __init__(self):
        self._steer_manager = SteerManager()
        super().__init__()

    def steer(self, message: str) -> bool:
        """注入转向消息

        Args:
            message: 要注入的提示内容

        Returns:
            True 如果成功
        """
        return self._steer_manager.steer(message)

    def _inject_steer_into_context(self, current_messages: list) -> list:
        """将转向消息注入到上下文中

        在工具调用完成后调用，在下一个用户消息前插入转向提示。

        Args:
            current_messages: 当前消息列表

        Returns:
            更新后的消息列表
        """
        steer_msg = self._steer_manager.consume_steer()
        if steer_msg is None:
            return current_messages

        steer_content = f"\n\n[Steer from Prometheus]: {steer_msg}\n\nPlease acknowledge this guidance and adjust your approach accordingly."

        if current_messages and current_messages[-1].get("role") == "user":
            current_messages[-1]["content"] += steer_content
        else:
            current_messages.append({"role": "user", "content": steer_content})

        return current_messages

    def has_pending_steer(self) -> bool:
        """检查是否有待处理的转向消息"""
        return self._steer_manager.has_pending_steer


_steer_manager_instance: SteerManager | None = None
_steer_lock = threading.Lock()


def get_steer_manager() -> SteerManager:
    """获取全局转向管理器实例"""
    global _steer_manager_instance
    with _steer_lock:
        if _steer_manager_instance is None:
            _steer_manager_instance = SteerManager()
        return _steer_manager_instance


def cmd_steer(message: str) -> bool:
    """命令行 /steer 命令处理器

    Args:
        message: 要注入的提示内容

    Returns:
        True 如果成功
    """
    manager = get_steer_manager()
    success = manager.steer(message)
    if success:
        print(
            f"  ⏩ Steer queued — arrives after the next tool call: {message[:80]}{'...' if len(message) > 80 else ''}"
        )
    else:
        print("  Usage: /steer <prompt>")
    return success
