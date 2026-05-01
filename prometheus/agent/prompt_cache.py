"""Prompt caching utilities for Prometheus."""

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cached prompt entry."""

    key: str
    response: Any
    timestamp: float
    ttl: int
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    hit_count: int = 1

    def is_expired(self) -> bool:
        """Check if the entry has expired."""
        return time.time() > self.timestamp + self.ttl

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "key": self.key,
            "response": self.response,
            "timestamp": self.timestamp,
            "ttl": self.ttl,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "hit_count": self.hit_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CacheEntry":
        """Create from dictionary."""
        return cls(
            key=data["key"],
            response=data["response"],
            timestamp=data["timestamp"],
            ttl=data["ttl"],
            model=data["model"],
            prompt_tokens=data.get("prompt_tokens", 0),
            completion_tokens=data.get("completion_tokens", 0),
            hit_count=data.get("hit_count", 1),
        )


class PromptCache:
    """Prompt cache manager.

    Supports:
    - In-memory caching with LRU eviction
    - Persistence to disk
    - TTL-based expiration
    - Per-model caching
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._cache = {}
            cls._instance._max_size = 1000
            cls._instance._default_ttl = 3600  # 1 hour
            cls._instance._persist_path = None
            cls._instance._persist_interval = 60
            cls._instance._last_persist = 0
        return cls._instance

    def configure(
        self,
        max_size: int = 1000,
        default_ttl: int = 3600,
        persist_path: str | None = None,
        persist_interval: int = 60,
    ):
        """Configure cache settings."""
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._persist_path = persist_path
        self._persist_interval = persist_interval

        if self._persist_path:
            self._load_from_disk()

    def _generate_key(self, prompt: str, model: str, **kwargs) -> str:
        """Generate a unique cache key."""
        data = {
            "prompt": prompt,
            "model": model,
            "kwargs": kwargs,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def get(self, prompt: str, model: str, **kwargs) -> Any | None:
        """Get a cached response."""
        key = self._generate_key(prompt, model, **kwargs)

        if key in self._cache:
            entry = self._cache[key]

            if entry.is_expired():
                del self._cache[key]
                return None

            entry.hit_count += 1
            return entry.response

        return None

    def set(
        self,
        prompt: str,
        model: str,
        response: Any,
        ttl: int | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        **kwargs,
    ):
        """Store a response in the cache."""
        key = self._generate_key(prompt, model, **kwargs)

        # Evict if full
        if len(self._cache) >= self._max_size:
            self._evict()

        entry = CacheEntry(
            key=key,
            response=response,
            timestamp=time.time(),
            ttl=ttl or self._default_ttl,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

        self._cache[key] = entry

        # Persist to disk if configured
        self._maybe_persist()

    def _evict(self):
        """Evict oldest entries."""
        # Evict 10% of entries
        evict_count = max(1, int(self._max_size * 0.1))

        # Sort by timestamp and evict oldest
        sorted_entries = sorted(self._cache.values(), key=lambda x: x.timestamp)

        for entry in sorted_entries[:evict_count]:
            del self._cache[entry.key]

        logger.debug(f"Evicted {evict_count} cache entries")

    def _maybe_persist(self):
        """Persist to disk if interval has passed."""
        if not self._persist_path:
            return

        now = time.time()
        if now - self._last_persist >= self._persist_interval:
            self._save_to_disk()
            self._last_persist = now

    def _save_to_disk(self):
        """Save cache to disk."""
        try:
            data = [entry.to_dict() for entry in self._cache.values()]

            with open(self._persist_path, "w") as f:
                json.dump(data, f)

            logger.debug(f"Saved {len(data)} cache entries to {self._persist_path}")
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    def _load_from_disk(self):
        """Load cache from disk."""
        try:
            with open(self._persist_path) as f:
                data = json.load(f)

            for entry_data in data:
                entry = CacheEntry.from_dict(entry_data)

                if not entry.is_expired():
                    self._cache[entry.key] = entry

            logger.debug(f"Loaded {len(self._cache)} cache entries from {self._persist_path}")
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.error(f"Failed to load cache: {e}")

    def clear(self):
        """Clear the cache."""
        self._cache.clear()
        logger.debug("Cache cleared")

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_hits = sum(entry.hit_count for entry in self._cache.values())
        expired_count = sum(1 for entry in self._cache.values() if entry.is_expired())

        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "total_hits": total_hits,
            "expired_count": expired_count,
            "persist_path": self._persist_path,
        }

    def prune_expired(self):
        """Remove expired entries."""
        expired_keys = [k for k, entry in self._cache.items() if entry.is_expired()]

        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.debug(f"Pruned {len(expired_keys)} expired entries")


def get_prompt_cache() -> PromptCache:
    """Get global prompt cache instance."""
    return PromptCache()


class CacheMiddleware:
    """Middleware for caching AI responses."""

    def __init__(self, cache: PromptCache = None):
        self._cache = cache or get_prompt_cache()

    async def process_request(self, prompt: str, model: str, **kwargs) -> tuple[Any, bool]:
        """Process a request through the cache.

        Returns:
            (response, was_cached)
        """
        cached = self._cache.get(prompt, model, **kwargs)

        if cached is not None:
            logger.debug(f"Cache hit for model {model}")
            return cached, True

        return None, False

    def process_response(self, prompt: str, model: str, response: Any, **kwargs):
        """Cache the response."""
        self._cache.set(prompt, model, response, **kwargs)


def enable_prompt_caching():
    """Enable prompt caching with default settings."""
    cache = get_prompt_cache()
    cache.configure(
        max_size=1000,
        default_ttl=3600,
    )
    logger.info("Prompt caching enabled")
