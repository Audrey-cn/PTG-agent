from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from prometheus.config import get_prometheus_home


class SessionContext:
    def __init__(self):
        self._contexts: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._base_path = get_prometheus_home() / "sessions"
        self._ensure_base_path()
    
    def _ensure_base_path(self):
        if not self._base_path.exists():
            self._base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_context_path(self, session_id: str) -> Path:
        return self._base_path / session_id / "context.json"
    
    def _load_from_disk(self, session_id: str) -> Dict[str, Any]:
        context_path = self._get_context_path(session_id)
        if context_path.exists():
            try:
                with open(context_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def _save_to_disk(self, session_id: str, context: Dict[str, Any]):
        context_path = self._get_context_path(session_id)
        context_path.parent.mkdir(parents=True, exist_ok=True)
        with open(context_path, "w", encoding="utf-8") as f:
            json.dump(context, f, ensure_ascii=False, indent=2)
    
    def get(self, session_id: str, key: str, default: Any = None) -> Any:
        with self._lock:
            if session_id not in self._contexts:
                self._contexts[session_id] = self._load_from_disk(session_id)
            return self._contexts[session_id].get(key, default)
    
    def set(self, session_id: str, key: str, value: Any):
        with self._lock:
            if session_id not in self._contexts:
                self._contexts[session_id] = self._load_from_disk(session_id)
            self._contexts[session_id][key] = value
            self._save_to_disk(session_id, self._contexts[session_id])
    
    def delete(self, session_id: str, key: str):
        with self._lock:
            if session_id not in self._contexts:
                self._contexts[session_id] = self._load_from_disk(session_id)
            if key in self._contexts[session_id]:
                del self._contexts[session_id][key]
                self._save_to_disk(session_id, self._contexts[session_id])
    
    def clear(self, session_id: str):
        with self._lock:
            self._contexts[session_id] = {}
            context_path = self._get_context_path(session_id)
            if context_path.exists():
                context_path.unlink()
    
    def get_all(self, session_id: str) -> Dict[str, Any]:
        with self._lock:
            if session_id not in self._contexts:
                self._contexts[session_id] = self._load_from_disk(session_id)
            return dict(self._contexts[session_id])
    
    def session_exists(self, session_id: str) -> bool:
        with self._lock:
            if session_id in self._contexts:
                return True
            context_path = self._get_context_path(session_id)
            return context_path.exists()
    
    def list_sessions(self) -> list:
        with self._lock:
            sessions = set(self._contexts.keys())
            if self._base_path.exists():
                for path in self._base_path.iterdir():
                    if path.is_dir() and (path / "context.json").exists():
                        sessions.add(path.name)
            return list(sessions)
    
    def delete_session(self, session_id: str):
        with self._lock:
            if session_id in self._contexts:
                del self._contexts[session_id]
            context_path = self._get_context_path(session_id)
            if context_path.exists():
                context_path.unlink()
            session_dir = context_path.parent
            if session_dir.exists() and not any(session_dir.iterdir()):
                session_dir.rmdir()


session_context = SessionContext()
