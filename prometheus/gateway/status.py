from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field


@dataclass
class GatewayStatus:
    running: bool = False
    started_at: float = 0.0
    active_sessions: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    errors: int = 0


class StatusTracker:
    def __init__(self) -> None:
        self._status = GatewayStatus()
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            self._status.running = True
            self._status.started_at = time.time()
            self._status.active_sessions = 0
            self._status.messages_sent = 0
            self._status.messages_received = 0
            self._status.errors = 0

    def stop(self) -> None:
        with self._lock:
            self._status.running = False

    def record_message_sent(self) -> None:
        with self._lock:
            self._status.messages_sent += 1

    def record_message_received(self) -> None:
        with self._lock:
            self._status.messages_received += 1

    def record_error(self) -> None:
        with self._lock:
            self._status.errors += 1

    def set_active_sessions(self, count: int) -> None:
        with self._lock:
            self._status.active_sessions = count

    def get_status(self) -> GatewayStatus:
        with self._lock:
            return GatewayStatus(
                running=self._status.running,
                started_at=self._status.started_at,
                active_sessions=self._status.active_sessions,
                messages_sent=self._status.messages_sent,
                messages_received=self._status.messages_received,
                errors=self._status.errors,
            )
