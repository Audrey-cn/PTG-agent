from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FooterMetrics:
    uptime_seconds: float = 0.0
    messages_processed: int = 0
    active_sessions: int = 0
    errors_count: int = 0
    last_message_time: float = 0.0
    custom_metrics: dict[str, Any] = field(default_factory=dict)


class RuntimeFooter:
    def __init__(self) -> None:
        self._start_time = time.time()
        self._metrics = FooterMetrics()
        self._lock = threading.Lock()

    def _format_uptime(self, seconds: float) -> str:
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m{secs}s"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h{minutes}m"
        else:
            days = int(seconds / 86400)
            hours = int((seconds % 86400) / 3600)
            return f"{days}d{hours}h"

    def generate_footer(self) -> str:
        with self._lock:
            uptime = time.time() - self._start_time
            self._metrics.uptime_seconds = uptime
            parts = [
                f"Uptime: {self._format_uptime(uptime)}",
                f"Messages: {self._metrics.messages_processed}",
                f"Sessions: {self._metrics.active_sessions}",
                f"Errors: {self._metrics.errors_count}",
            ]
            return " | ".join(parts)

    def update_metric(self, key: str, value: Any) -> None:
        with self._lock:
            if key == "messages_processed":
                self._metrics.messages_processed = int(value)
            elif key == "active_sessions":
                self._metrics.active_sessions = int(value)
            elif key == "errors_count":
                self._metrics.errors_count = int(value)
            elif key == "last_message_time":
                self._metrics.last_message_time = float(value)
            else:
                self._metrics.custom_metrics[key] = value

    def get_metrics(self) -> dict[str, Any]:
        with self._lock:
            return {
                "uptime_seconds": time.time() - self._start_time,
                "messages_processed": self._metrics.messages_processed,
                "active_sessions": self._metrics.active_sessions,
                "errors_count": self._metrics.errors_count,
                "last_message_time": self._metrics.last_message_time,
                "custom_metrics": self._metrics.custom_metrics.copy(),
            }

    def increment_messages(self) -> None:
        with self._lock:
            self._metrics.messages_processed += 1
            self._metrics.last_message_time = time.time()

    def increment_errors(self) -> None:
        with self._lock:
            self._metrics.errors_count += 1
