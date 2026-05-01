from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from prometheus.gateway.config import GatewayConfig


@dataclass
class Session:
    id: str
    platform: str
    chat_id: str
    user: str
    history: list[Dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SessionManager:
    def __init__(self, config: GatewayConfig | None = None):
        self._config = config or GatewayConfig()
        self._sessions: Dict[str, Session] = {}
        self._lock = threading.Lock()

    def create_session(self, platform: str, chat_id: str, user: str) -> Session:
        with self._lock:
            session_id = str(uuid.uuid4())
            session = Session(
                id=session_id,
                platform=platform,
                chat_id=chat_id,
                user=user,
            )
            self._sessions[session_id] = session
            return session

    def get_session(self, session_id: str) -> Session | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.last_active = time.time()
            return session

    def get_or_create(self, platform: str, chat_id: str, user: str) -> Session:
        with self._lock:
            for session in self._sessions.values():
                if session.platform == platform and session.chat_id == chat_id:
                    session.last_active = time.time()
                    return session
        return self.create_session(platform, chat_id, user)

    def close_session(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def list_active(self) -> list[Session]:
        with self._lock:
            return list(self._sessions.values())

    def cleanup_expired(self, timeout: Optional[int] = None) -> int:
        timeout = timeout or self._config.session_timeout
        now = time.time()
        expired_ids: List[str] = []
        with self._lock:
            for sid, session in self._sessions.items():
                if now - session.last_active > timeout:
                    expired_ids.append(sid)
            for sid in expired_ids:
                del self._sessions[sid]
        return len(expired_ids)
