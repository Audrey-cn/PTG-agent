from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger("prometheus.acp_adapter.session")


@dataclass
class SessionInfo:
    session_id: str
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    metadata: dict[str, str] = field(default_factory=dict)
    active: bool = True


class ACPSession:
    def __init__(self, max_sessions: int = 100, ttl: float = 3600.0) -> None:
        self._sessions: dict[str, SessionInfo] = {}
        self._max_sessions = max_sessions
        self._ttl = ttl

    def create(self, metadata: dict[str, str] | None = None) -> SessionInfo:
        self._evict_expired()

        if len(self._sessions) >= self._max_sessions:
            oldest_id = min(self._sessions, key=lambda k: self._sessions[k].last_active)
            del self._sessions[oldest_id]

        session_id = uuid.uuid4().hex
        info = SessionInfo(
            session_id=session_id,
            metadata=metadata or {},
        )
        self._sessions[session_id] = info
        logger.info("Created ACP session: %s", session_id)
        return info

    def get(self, session_id: str) -> SessionInfo | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None

        if not session.active:
            return None

        if time.time() - session.last_active > self._ttl:
            del self._sessions[session_id]
            return None

        session.last_active = time.time()
        return session

    def close(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session is None:
            return False

        session.active = False
        logger.info("Closed ACP session: %s", session_id)
        return True

    def list_active(self) -> list[SessionInfo]:
        now = time.time()
        active = []
        for sid in list(self._sessions.keys()):
            session = self._sessions[sid]
            if session.active and now - session.last_active <= self._ttl:
                active.append(session)
            elif now - session.last_active > self._ttl:
                del self._sessions[sid]
        return active

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [sid for sid, s in self._sessions.items() if now - s.last_active > self._ttl]
        for sid in expired:
            del self._sessions[sid]
