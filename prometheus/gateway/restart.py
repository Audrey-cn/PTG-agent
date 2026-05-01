from __future__ import annotations

import json
import time
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from prometheus.config import get_prometheus_home


@dataclass
class RestartState:
    pending: bool = False
    prepared_at: float = 0.0
    sessions: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class GatewayRestart:
    def __init__(self) -> None:
        self._state = RestartState()
        self._lock = threading.Lock()
        self._session_manager: Any = None

    def set_session_manager(self, manager: Any) -> None:
        self._session_manager = manager

    def _state_path(self) -> Path:
        return get_prometheus_home() / "gateway_restart_state.json"

    def prepare_restart(self) -> bool:
        with self._lock:
            if self._state.pending:
                return False
            self._state.pending = True
            self._state.prepared_at = time.time()
            if self._session_manager is not None:
                for session in self._session_manager.list_active():
                    self._state.sessions.append({
                        "id": session.id,
                        "platform": session.platform,
                        "chat_id": session.chat_id,
                        "user": session.user,
                        "metadata": session.metadata,
                    })
            state_data = {
                "pending": self._state.pending,
                "prepared_at": self._state.prepared_at,
                "sessions": self._state.sessions,
                "metadata": self._state.metadata,
            }
            path = self._state_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(state_data, f)
            return True

    def execute_restart(self) -> bool:
        with self._lock:
            if not self._state.pending:
                return False
            path = self._state_path()
            if path.exists():
                path.unlink()
            self._state = RestartState()
            return True

    def cancel_restart(self) -> bool:
        with self._lock:
            if not self._state.pending:
                return False
            path = self._state_path()
            if path.exists():
                path.unlink()
            self._state = RestartState()
            return True

    def is_restart_pending(self) -> bool:
        with self._lock:
            return self._state.pending

    def get_saved_sessions(self) -> list[dict[str, Any]]:
        path = self._state_path()
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data.get("sessions", [])
            except Exception:
                pass
        return []
