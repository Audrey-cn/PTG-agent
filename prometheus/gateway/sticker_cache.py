from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from prometheus.config import get_prometheus_home


@dataclass
class StickerEntry:
    platform: str
    sticker_id: str
    file_path: str
    cached_at: float
    size: int = 0
    checksum: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class StickerCache:
    def __init__(self) -> None:
        self._cache: dict[str, StickerEntry] = {}
        self._lock = threading.Lock()

    def _cache_dir(self) -> Path:
        path = get_prometheus_home() / "sticker_cache"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _cache_key(self, platform: str, sticker_id: str) -> str:
        return f"{platform}:{sticker_id}"

    def _compute_checksum(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()[:16]

    def cache_sticker(self, platform: str, sticker_id: str, file_path: str) -> bool:
        try:
            source_path = Path(file_path)
            if not source_path.exists():
                return False
            data = source_path.read_bytes()
            checksum = self._compute_checksum(data)
            cache_dir = self._cache_dir()
            ext = source_path.suffix or ".bin"
            cached_filename = f"{platform}_{sticker_id}{ext}"
            cached_path = cache_dir / cached_filename
            cached_path.write_bytes(data)
            with self._lock:
                key = self._cache_key(platform, sticker_id)
                self._cache[key] = StickerEntry(
                    platform=platform,
                    sticker_id=sticker_id,
                    file_path=str(cached_path),
                    cached_at=time.time(),
                    size=len(data),
                    checksum=checksum,
                )
            return True
        except Exception:
            return False

    def get_sticker(self, platform: str, sticker_id: str) -> bytes | None:
        with self._lock:
            key = self._cache_key(platform, sticker_id)
            entry = self._cache.get(key)
            if not entry:
                return None
        try:
            path = Path(entry.file_path)
            if path.exists():
                return path.read_bytes()
        except Exception:
            pass
        return None

    def list_stickers(self, platform: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            results = []
            for entry in self._cache.values():
                if platform is None or entry.platform == platform:
                    results.append({
                        "platform": entry.platform,
                        "sticker_id": entry.sticker_id,
                        "file_path": entry.file_path,
                        "cached_at": entry.cached_at,
                        "size": entry.size,
                        "checksum": entry.checksum,
                    })
            return results

    def clear_cache(self) -> int:
        with self._lock:
            count = len(self._cache)
            cache_dir = self._cache_dir()
            for entry in self._cache.values():
                try:
                    path = Path(entry.file_path)
                    if path.exists():
                        path.unlink()
                except Exception:
                    pass
            self._cache.clear()
        return count

    def cache_from_bytes(
        self,
        platform: str,
        sticker_id: str,
        data: bytes,
        ext: str = ".bin",
    ) -> bool:
        try:
            checksum = self._compute_checksum(data)
            cache_dir = self._cache_dir()
            cached_filename = f"{platform}_{sticker_id}{ext}"
            cached_path = cache_dir / cached_filename
            cached_path.write_bytes(data)
            with self._lock:
                key = self._cache_key(platform, sticker_id)
                self._cache[key] = StickerEntry(
                    platform=platform,
                    sticker_id=sticker_id,
                    file_path=str(cached_path),
                    cached_at=time.time(),
                    size=len(data),
                    checksum=checksum,
                )
            return True
        except Exception:
            return False
