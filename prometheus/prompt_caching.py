from __future__ import annotations

import contextlib
import hashlib
import json
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

from prometheus.config import get_prometheus_home

if TYPE_CHECKING:
    from pathlib import Path


class PromptCache:
    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        self._cache_dir = cache_dir or get_prometheus_home() / "prompt_cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._stats: Dict[str, int] = {"hits": 0, "misses": 0}
        self._cache_index: Dict[str, Dict[str, Any]] = {}
        self._load_index()

    def _load_index(self) -> None:
        index_file = self._cache_dir / "index.json"
        if index_file.exists():
            try:
                with open(index_file) as f:
                    self._cache_index = json.load(f)
            except (OSError, json.JSONDecodeError):
                self._cache_index = {}

    def _save_index(self) -> None:
        index_file = self._cache_dir / "index.json"
        try:
            with open(index_file, "w") as f:
                json.dump(self._cache_index, f, indent=2)
        except OSError:
            pass

    def get_cache_key(
        self, messages: list[Dict[str, Any]], tools: list[Dict[str, Any]] | None = None
    ) -> str:
        content = json.dumps({"messages": messages, "tools": tools or []}, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def check_cache(self, key: str) -> Dict[str, Any] | None:
        if key not in self._cache_index:
            self._stats["misses"] += 1
            return None

        cache_file = self._cache_dir / f"{key}.json"
        if not cache_file.exists():
            del self._cache_index[key]
            self._save_index()
            self._stats["misses"] += 1
            return None

        try:
            with open(cache_file) as f:
                cached_data = json.load(f)
        except (OSError, json.JSONDecodeError):
            self._stats["misses"] += 1
            return None

        ttl = cached_data.get("ttl", 3600)
        created_at = cached_data.get("created_at", 0)
        if time.time() - created_at > ttl:
            self.invalidate(key)
            self._stats["misses"] += 1
            return None

        self._stats["hits"] += 1
        return cached_data.get("response")

    def store_cache(self, key: str, response: Dict[str, Any], ttl: int = 3600) -> None:
        cache_file = self._cache_dir / f"{key}.json"
        cache_data = {
            "key": key,
            "response": response,
            "created_at": time.time(),
            "ttl": ttl,
            "timestamp": datetime.now().isoformat(),
        }

        try:
            with open(cache_file, "w") as f:
                json.dump(cache_data, f, indent=2)

            self._cache_index[key] = {
                "created_at": cache_data["created_at"],
                "ttl": ttl,
            }
            self._save_index()
        except OSError:
            pass

    def invalidate(self, key: str) -> None:
        cache_file = self._cache_dir / f"{key}.json"
        if cache_file.exists():
            with contextlib.suppress(OSError):
                cache_file.unlink()

        if key in self._cache_index:
            del self._cache_index[key]
            self._save_index()

    def invalidate_all(self) -> None:
        for key in list(self._cache_index.keys()):
            self.invalidate(key)

    def get_cache_stats(self) -> Dict[str, Any]:
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0.0

        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "total": total,
            "hit_rate": round(hit_rate, 2),
            "cache_size": len(self._cache_index),
        }

    def add_cache_control(
        self, messages: list[Dict[str, Any]], cache_type: str = "ephemeral"
    ) -> list[Dict[str, Any]]:
        enhanced_messages = []

        for i, msg in enumerate(messages):
            enhanced_msg = dict(msg)

            if i == len(messages) - 1 and msg.get("role") == "user":
                if isinstance(enhanced_msg.get("content"), str):
                    enhanced_msg["content"] = [
                        {"type": "text", "text": enhanced_msg["content"]},
                        {"type": "cache_control", "cache_type": cache_type},
                    ]
                elif isinstance(enhanced_msg.get("content"), list):
                    enhanced_msg["content"].append(
                        {"type": "cache_control", "cache_type": cache_type}
                    )

            enhanced_messages.append(enhanced_msg)

        return enhanced_messages

    def get_cached_response_for_messages(
        self, messages: list[Dict[str, Any]], tools: list[Dict[str, Any]] | None = None
    ) -> Dict[str, Any] | None:
        key = self.get_cache_key(messages, tools)
        return self.check_cache(key)

    def store_response_for_messages(
        self,
        messages: list[Dict[str, Any]],
        response: Dict[str, Any],
        tools: list[Dict[str, Any]] | None = None,
        ttl: int = 3600,
    ) -> str:
        key = self.get_cache_key(messages, tools)
        self.store_cache(key, response, ttl)
        return key

    def cleanup_expired(self) -> int:
        expired_keys = []
        current_time = time.time()

        for key, meta in self._cache_index.items():
            created_at = meta.get("created_at", 0)
            ttl = meta.get("ttl", 3600)
            if current_time - created_at > ttl:
                expired_keys.append(key)

        for key in expired_keys:
            self.invalidate(key)

        return len(expired_keys)
