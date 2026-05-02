"""🔔 Webhook 直推工具."""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class WebhookPayload:
    """Webhook 载荷"""

    event: str
    data: dict[str, Any]
    timestamp: str | None = None


class WebhookTool:
    """Webhook 工具"""

    def __init__(self):
        self._handlers: dict[str, list] = {}
        self._lock = threading.Lock()

    def register_handler(self, event: str, handler: callable):
        """注册事件处理器"""
        with self._lock:
            if event not in self._handlers:
                self._handlers[event] = []
            self._handlers[event].append(handler)

    def send(
        self,
        url: str,
        event: str,
        data: dict[str, Any],
        headers: dict[str, str] | None = None,
        method: str = "POST",
    ) -> dict[str, Any]:
        """直接发送 Webhook 请求

        Args:
            url: Webhook URL
            event: 事件类型
            data: 载荷数据
            headers: 自定义请求头
            method: HTTP 方法

        Returns:
            {"success": True, "status_code": 200} 或 {"success": False, "error": "..."}
        """
        if not self._validate_url(url):
            return {"success": False, "error": "Invalid URL"}

        payload = WebhookPayload(
            event=event,
            data=data,
            timestamp=self._get_timestamp(),
        )

        serialized = json.dumps(payload.__dict__, default=str)

        default_headers = {
            "Content-Type": "application/json",
            "User-Agent": "Prometheus-Webhook/1.0",
        }
        if headers:
            default_headers.update(headers)

        try:
            import urllib.request

            req = urllib.request.Request(
                url,
                data=serialized.encode("utf-8"),
                headers=default_headers,
                method=method,
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                status_code = response.status
                response_body = response.read().decode("utf-8")

                if 200 <= status_code < 300:
                    return {
                        "success": True,
                        "status_code": status_code,
                        "response": response_body[:500] if response_body else None,
                    }
                else:
                    return {
                        "success": False,
                        "status_code": status_code,
                        "error": f"HTTP {status_code}: {response_body[:200]}",
                    }

        except urllib.error.URLError as e:
            return {"success": False, "error": f"URL Error: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _validate_url(self, url: str) -> bool:
        """验证 URL 格式"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    def _get_timestamp(self) -> str:
        """获取当前时间戳"""

        return datetime.now(UTC).isoformat()

    def send_alert(
        self,
        url: str,
        alert_name: str,
        severity: str,
        message: str,
        **extra: Any,
    ) -> dict[str, Any]:
        """发送告警

        Args:
            url: Webhook URL
            alert_name: 告警名称
            severity: 严重程度 (info/warning/error/critical)
            message: 告警消息
            **extra: 额外数据
        """
        return self.send(
            url=url,
            event="alert",
            data={
                "alert": alert_name,
                "severity": severity,
                "message": message,
                **extra,
            },
        )

    def send_metrics(
        self,
        url: str,
        metric_name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """发送指标

        Args:
            url: Webhook URL
            metric_name: 指标名称
            value: 指标值
            tags: 标签
        """
        return self.send(
            url=url,
            event="metrics",
            data={
                "metric": metric_name,
                "value": value,
                "tags": tags or {},
            },
        )

    def send_log(
        self,
        url: str,
        level: str,
        message: str,
        source: str | None = None,
    ) -> dict[str, Any]:
        """发送日志

        Args:
            url: Webhook URL
            level: 日志级别 (debug/info/warning/error)
            message: 日志消息
            source: 来源
        """
        return self.send(
            url=url,
            event="log",
            data={
                "level": level,
                "message": message,
                "source": source or "prometheus",
            },
        )


_webhook_tool_instance: WebhookTool | None = None
_webhook_lock = threading.Lock()


def get_webhook_tool() -> WebhookTool:
    """获取全局 Webhook 工具实例"""
    global _webhook_tool_instance
    with _webhook_lock:
        if _webhook_tool_instance is None:
            _webhook_tool_instance = WebhookTool()
        return _webhook_tool_instance


def send_alert(url: str, alert_name: str, severity: str, message: str, **kwargs) -> dict[str, Any]:
    """快捷函数：发送告警"""
    tool = get_webhook_tool()
    return tool.send_alert(url, alert_name, severity, message, **kwargs)


def send_metrics(
    url: str, metric_name: str, value: float, tags: dict[str, str] | None = None
) -> dict[str, Any]:
    """快捷函数：发送指标"""
    tool = get_webhook_tool()
    return tool.send_metrics(url, metric_name, value, tags)
