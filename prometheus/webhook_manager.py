from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger("prometheus.webhook_manager")


@dataclass
class WebhookSubscription:
    id: str
    url: str
    events: list[str]
    created_at: float
    last_triggered: float = 0.0
    failure_count: int = 0
    active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class WebhookManager:
    """Webhook管理器 - 订阅和管理webhook事件。

    支持订阅各种事件并在事件触发时调用webhook URL。
    """

    _instance: WebhookManager | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._subscriptions: dict[str, WebhookSubscription] = {}
        self._lock = threading.Lock()
        self._handlers: dict[str, list[Callable]] = {}

    @classmethod
    def get_instance(cls) -> WebhookManager:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def subscribe(self, url: str, events: list[str], metadata: dict[str, Any] | None = None) -> str:
        """订阅webhook事件。

        Args:
            url: Webhook URL
            events: 订阅的事件列表
            metadata: 可选的元数据

        Returns:
            Webhook订阅ID
        """
        import time

        with self._lock:
            sub_id = str(uuid.uuid4())[:8]
            self._subscriptions[sub_id] = WebhookSubscription(
                id=sub_id,
                url=url,
                events=events,
                created_at=time.time(),
                metadata=metadata or {},
            )
            logger.info(f"Subscribed to webhook: {url} for events: {events}")
            return sub_id

    def unsubscribe(self, url: str) -> bool:
        """取消订阅webhook。

        Args:
            url: Webhook URL

        Returns:
            是否成功
        """
        with self._lock:
            for sub_id, sub in list(self._subscriptions.items()):
                if sub.url == url:
                    del self._subscriptions[sub_id]
                    logger.info(f"Unsubscribed from webhook: {url}")
                    return True
            return False

    def list_webhooks(self) -> list[dict[str, Any]]:
        """列出所有webhook订阅。"""
        with self._lock:
            return [
                {
                    "id": sub.id,
                    "url": sub.url,
                    "events": sub.events,
                    "created_at": sub.created_at,
                    "last_triggered": sub.last_triggered,
                    "active": sub.active,
                    "failure_count": sub.failure_count,
                }
                for sub in self._subscriptions.values()
            ]

    def trigger(self, event: str, data: dict[str, Any]) -> int:
        """触发webhook事件。

        Args:
            event: 事件名称
            data: 事件数据

        Returns:
            成功触发的数量
        """
        import time

        triggered = 0
        with self._lock:
            for sub in self._subscriptions.values():
                if not sub.active:
                    continue
                if "*" not in sub.events and event not in sub.events:
                    continue

                try:
                    self._send_webhook(sub.url, event, data)
                    sub.last_triggered = time.time()
                    sub.failure_count = 0
                    triggered += 1
                except Exception as e:
                    logger.error(f"Failed to trigger webhook {sub.url}: {e}")
                    sub.failure_count += 1
                    if sub.failure_count >= 3:
                        sub.active = False

        return triggered

    def _send_webhook(self, url: str, event: str, data: dict[str, Any]) -> None:
        """发送webhook请求。"""
        import urllib.request

        payload = json.dumps(
            {
                "event": event,
                "timestamp": time.time(),
                "data": data,
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.debug(f"Webhook sent to {url}: {resp.status}")
        except Exception as e:
            logger.error(f"Webhook request failed: {e}")
            raise

    def test_webhook(self, url: str, event: str = "test") -> bool:
        """测试webhook URL。

        Args:
            url: Webhook URL
            event: 测试事件名称

        Returns:
            是否成功
        """
        try:
            self._send_webhook(url, event, {"test": True, "message": "Prometheus webhook test"})
            return True
        except Exception as e:
            logger.error(f"Webhook test failed: {e}")
            return False

    def register_handler(self, event: str, handler: Callable) -> None:
        """注册事件处理器。

        Args:
            event: 事件名称
            handler: 处理函数
        """
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)

    def get_webhook_count(self) -> int:
        """获取webhook数量。"""
        return len(self._subscriptions)


def get_webhook_manager() -> WebhookManager:
    """获取WebhookManager单例。"""
    return WebhookManager.get_instance()
