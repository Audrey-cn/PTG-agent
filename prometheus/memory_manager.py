from __future__ import annotations

import json
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from prometheus.config import get_prometheus_home
from prometheus.memory_provider import MemoryProvider, FileMemoryProvider

logger = logging.getLogger("prometheus.memory_manager")


class MemoryManager:
    def __init__(self, provider: MemoryProvider | None = None):
        memories_dir = get_prometheus_home() / "memories"
        memories_dir.mkdir(parents=True, exist_ok=True)
        self._provider = provider or FileMemoryProvider(base_dir=memories_dir)
        self._lock = threading.Lock()

    def store(self, key: str, value: str, metadata: dict | None = None) -> bool:
        with self._lock:
            entry = {
                "key": key,
                "value": value,
                "metadata": metadata or {},
                "stored_at": datetime.now().isoformat(),
            }
            return self._provider.store(key, entry)

    def retrieve(self, key: str) -> dict | None:
        with self._lock:
            return self._provider.retrieve(key)

    def search(self, query: str, limit: int = 10) -> list[dict]:
        with self._lock:
            return self._provider.search(query, limit=limit)

    def summarize_conversation(self, messages: list[dict]) -> str:
        if not messages:
            return ""
        parts: list[str] = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, list):
                text_chunks = [
                    c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"
                ]
                content = " ".join(text_chunks)
            if content:
                parts.append(f"[{role}] {content.strip()}")
        full = "\n".join(parts)
        if len(full) <= 500:
            return full
        sentences = full.replace("\n", " ").split("。")
        if len(sentences) <= 3:
            return full[:500]
        first = sentences[0]
        last = sentences[-1] if sentences[-1].strip() else sentences[-2]
        mid_count = max(1, len(sentences) // 3)
        mid_idx = len(sentences) // 2
        mid = "。".join(sentences[mid_idx : mid_idx + mid_count])
        return f"{first}。 ... {mid}。 ... {last}。"

    def extract_important_facts(self, messages: list[dict]) -> list[str]:
        facts: list[str] = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                text_chunks = [
                    c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"
                ]
                content = " ".join(text_chunks)
            if not isinstance(content, str):
                continue
            for sentence in content.replace("\n", " ").split("。"):
                s = sentence.strip()
                if not s:
                    continue
                for marker in ("重要", "注意", "关键", "必须", "不要", "禁止", "important", "note", "key", "must", "never"):
                    if marker in s.lower():
                        facts.append(s)
                        break
        return facts

    def get_recent(self, limit: int = 20) -> list[dict]:
        with self._lock:
            all_keys = self._provider.list_keys()
            entries: list[dict] = []
            for key in all_keys:
                entry = self._provider.retrieve(key)
                if entry is not None:
                    entries.append(entry)
            entries.sort(key=lambda e: e.get("stored_at", ""), reverse=True)
            return entries[:limit]

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._provider.delete(key)
