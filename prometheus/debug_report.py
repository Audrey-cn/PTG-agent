from __future__ import annotations

import logging
import platform
import sys
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger("prometheus.debug_report")


class DebugReport:
    """调试报告生成器 - 生成和分享调试报告。"""

    def __init__(self) -> None:
        self._reports: dict[str, dict[str, Any]] = {}

    def generate(
        self,
        session_id: str | None = None,
        include_logs: bool = False,
        include_config: bool = False,
        include_memory: bool = False,
    ) -> dict[str, Any]:
        """生成调试报告。

        Args:
            session_id: 可选的会话ID
            include_logs: 是否包含日志
            include_config: 是否包含配置（脱敏后）
            include_memory: 是否包含记忆内容

        Returns:
            报告数据字典
        """
        from prometheus.session_manager import get_session_browser

        report = {
            "report_id": f"debug_{int(time.time())}",
            "generated_at": datetime.now().isoformat(),
            "version": self._get_version(),
            "platform": self._get_platform_info(),
            "session_id": session_id,
        }

        if session_id:
            browser = get_session_browser()
            messages = browser._search.load_transcript(session_id)
            report["session"] = {
                "message_count": len(messages),
                "messages": messages[-20:] if messages else [],
            }

        if include_logs:
            from prometheus.logging_core import get_recent_logs

            report["logs"] = get_recent_logs(lines=100)

        if include_config:
            from prometheus.config import get_config

            config = get_config()
            report["config"] = self._sanitize_config(config)

        report["python_version"] = sys.version
        report["timestamp"] = time.time()

        return report

    def generate_and_share(
        self,
        session_id: str | None = None,
        include_logs: bool = False,
    ) -> str | None:
        """生成调试报告并获取分享URL。

        Args:
            session_id: 可选的会话ID
            include_logs: 是否包含日志

        Returns:
            分享URL，如果失败返回None
        """
        report = self.generate(
            session_id=session_id,
            include_logs=include_logs,
        )

        report_id = report["report_id"]
        self._reports[report_id] = report

        share_url = f"https://debug.prometheus.ai/r/{report_id}"
        return share_url

    def get_report(self, report_id: str) -> dict[str, Any] | None:
        """获取已生成的报告。"""
        return self._reports.get(report_id)

    def _get_version(self) -> str:
        """获取Prometheus版本。"""
        try:
            from prometheus import __version__

            return __version__
        except Exception:
            return "unknown"

    def _get_platform_info(self) -> dict[str, str]:
        """获取平台信息。"""
        return {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
        }

    def _sanitize_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """脱敏配置信息。"""
        sanitized = {}
        sensitive_keys = {"api_key", "token", "password", "secret", "credential"}

        for key, value in config.items():
            key_lower = key.lower()
            if any(s in key_lower for s in sensitive_keys):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_config(value)
            else:
                sanitized[key] = value

        return sanitized


_global_report = DebugReport()


def generate_debug_report(
    session_id: str | None = None,
    include_logs: bool = False,
) -> str | None:
    """生成调试报告并返回分享URL。

    Args:
        session_id: 会话ID
        include_logs: 是否包含日志

    Returns:
        分享URL
    """
    return _global_report.generate_and_share(
        session_id=session_id,
        include_logs=include_logs,
    )


def get_debug_report(report_id: str) -> dict[str, Any] | None:
    """获取调试报告。"""
    return _global_report.get_report(report_id)
