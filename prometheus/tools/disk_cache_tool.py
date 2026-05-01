"""Disk-based caching tool for expensive computations or external API calls."""

import hashlib
import json
import logging
import pickle
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from prometheus._paths import get_paths

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cached entry with metadata."""

    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    hit_count: int = 0
    ttl: float | None = None  # Time to live in seconds (None = never expire)


class DiskCache:
    """
    Disk-based key-value cache with TTL support.

    Stores cached data in files on disk, with optional time-to-live (TTL)
    expiration for automatic cleanup of stale data.
    """

    def __init__(self, cache_dir: str | None = None) -> None:
        """
        Initialize disk cache.

        Args:
            cache_dir: Directory for storing cache files (default: ~/.prometheus/cache)
        """
        if cache_dir is None:
            cache_dir = get_paths().cache
        else:
            cache_dir = Path(cache_dir)

        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._index_file = self._cache_dir / ".index.json"
        self._index: dict[str, dict[str, Any]] = self._load_index()
        self._default_ttl = 86400 * 7  # 7 days

    def _load_index(self) -> dict[str, dict[str, Any]]:
        """Load cache index from disk."""
        if not self._index_file.exists():
            return {}

        try:
            with open(self._index_file) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load cache index: {e}")
            return {}

    def _save_index(self) -> None:
        """Save cache index to disk."""
        try:
            with open(self._index_file, "w") as f:
                json.dump(self._index, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save cache index: {e}")

    def _get_cache_path(self, key: str) -> Path:
        """Get the file path for a cached key."""
        # Hash key for safe filename
        key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self._cache_dir / f"{key_hash}.cache"

    def set(self, key: str, value: Any, ttl: float | None = None) -> bool:
        """
        Set a value in the cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (None = use default)

        Returns:
            True if successful
        """
        try:
            cache_path = self._get_cache_path(key)

            with open(cache_path, "wb") as f:
                pickle.dump(value, f)

            self._index[key] = {
                "created_at": time.time(),
                "last_accessed": time.time(),
                "hit_count": 0,
                "ttl": ttl if ttl is not None else self._default_ttl,
                "size_bytes": cache_path.stat().st_size,
            }
            self._save_index()
            logger.debug(f"Cached: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to cache {key}: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the cache.

        Args:
            key: Cache key
            default: Value to return if key not found

        Returns:
            Cached value or default
        """
        if key not in self._index:
            return default

        entry = self._index[key]

        if entry["ttl"] is not None and entry["ttl"] > 0:
            if time.time() - entry["created_at"] > entry["ttl"]:
                logger.debug(f"Cache expired: {key}")
                self.delete(key)
                return default

        try:
            cache_path = self._get_cache_path(key)
            with open(cache_path, "rb") as f:
                value = pickle.load(f)

            entry["last_accessed"] = time.time()
            entry["hit_count"] += 1
            self._save_index()

            logger.debug(f"Cache hit: {key}")
            return value
        except Exception as e:
            logger.error(f"Failed to load cached {key}: {e}")
            self.delete(key)
            return default

    def delete(self, key: str) -> bool:
        """
        Delete a cached value.

        Args:
            key: Cache key

        Returns:
            True if deleted
        """
        if key not in self._index:
            return False

        try:
            cache_path = self._get_cache_path(key)
            if cache_path.exists():
                cache_path.unlink()

            del self._index[key]
            self._save_index()
            logger.debug(f"Deleted cache: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete cache {key}: {e}")
            return False

    def exists(self, key: str) -> bool:
        """
        Check if a key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if key exists and not expired
        """
        if key not in self._index:
            return False

        entry = self._index[key]

        if entry["ttl"] is not None and entry["ttl"] > 0:
            if time.time() - entry["created_at"] > entry["ttl"]:
                return False

        return True

    def clear(self) -> bool:
        """
        Clear all cached data.

        Returns:
            True if successful
        """
        try:
            for cache_file in self._cache_dir.glob("*.cache"):
                cache_file.unlink()

            self._index.clear()
            self._save_index()
            logger.info("Cache cleared")
            return True
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False

    def cleanup_expired(self) -> int:
        """
        Remove all expired cache entries.

        Returns:
            Number of entries removed
        """
        removed = 0
        keys_to_delete = []

        for key, entry in self._index.items():
            if entry["ttl"] is not None and entry["ttl"] > 0:
                if time.time() - entry["created_at"] > entry["ttl"]:
                    keys_to_delete.append(key)

        for key in keys_to_delete:
            self.delete(key)
            removed += 1

        logger.debug(f"Cleaned up {removed} expired cache entries")
        return removed

    def get_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with cache info
        """
        total_size = sum(entry["size_bytes"] for entry in self._index.values())
        total_hits = sum(entry["hit_count"] for entry in self._index.values())

        return {
            "entries": len(self._index),
            "total_size_bytes": total_size,
            "total_hits": total_hits,
            "cache_dir": str(self._cache_dir),
        }

    def list_keys(self, pattern: str | None = None) -> list[str]:
        """
        List all keys in cache.

        Args:
            pattern: Optional glob pattern to filter keys

        Returns:
            List of cache keys
        """
        import fnmatch

        keys = list(self._index.keys())
        if pattern:
            keys = fnmatch.filter(keys, pattern)
        return keys


# Global cache instance
_DEFAULT_CACHE: DiskCache | None = None


def get_cache() -> DiskCache:
    """Get or create the default disk cache instance."""
    global _DEFAULT_CACHE
    if _DEFAULT_CACHE is None:
        _DEFAULT_CACHE = DiskCache()
    return _DEFAULT_CACHE


def cached(key: str | None = None, ttl: float | None = None):
    """
    Decorator for caching function results.

    Args:
        key: Cache key pattern (uses args if None)
        ttl: Time to live in seconds

    Usage:
        @cached(ttl=3600)
        def expensive_function(x, y):
            return x + y
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            cache_key = key or f"{func.__module__}.{func.__name__}:{args}:{sorted(kwargs.items())}"
            cache = get_cache()

            result = cache.get(cache_key)
            if result is not None:
                return result

            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result

        return wrapper

    return decorator


def memoize(func):
    """
    Simple memoization decorator using disk cache.

    Same as @cached() with default TTL.

    Args:
        func: Function to memoize
    """

    def wrapper(*args, **kwargs):
        key = f"{func.__module__}.{func.__name__}:{args}:{sorted(kwargs.items())}"
        cache = get_cache()
        result = cache.get(key)
        if result is not None:
            return result
        result = func(*args, **kwargs)
        cache.set(key, result)
        return result

    return wrapper


if __name__ == "__main__":
    print("Disk Cache Demo")
    print("=" * 60)

    cache = DiskCache("/tmp/prometheus_test_cache")

    print("\n1. Setting values:")
    cache.set("test1", "Hello World!")
    cache.set("test2", {"key": "value"}, ttl=10)
    cache.set("test3", [1, 2, 3])

    print("\n2. Getting values:")
    print(cache.get("test1"))
    print(cache.get("test2"))
    print(cache.get("test3"))

    print("\n3. Stats:")
    stats = cache.get_stats()
    print(f"Entries: {stats['entries']}")
    print(f"Size: {stats['total_size_bytes']} bytes")

    print("\n4. List keys:")
    print(cache.list_keys())

    print("\n5. Delete test1:")
    cache.delete("test1")
    print(cache.get("test1", "NOT FOUND"))

    print("\n6. Clear cache:")
    cache.clear()
    print(f"Entries now: {len(cache.list_keys())}")
