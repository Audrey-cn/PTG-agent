from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

logger = logging.getLogger("prometheus.memory_provider")


class MemoryProvider(ABC):
    @abstractmethod
    def store(self, key: str, entry: dict) -> bool: ...

    @abstractmethod
    def retrieve(self, key: str) -> dict | None: ...

    @abstractmethod
    def search(self, query: str, limit: int = 10) -> list[dict]: ...

    @abstractmethod
    def delete(self, key: str) -> bool: ...

    @abstractmethod
    def list_keys(self) -> list[str]: ...


class FileMemoryProvider(MemoryProvider):
    def __init__(self, base_dir: Path | str):
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", key)
        return self._base_dir / f"{safe}.json"

    def store(self, key: str, entry: dict) -> bool:
        try:
            path = self._path_for(key)
            path.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except Exception as e:
            logger.error("FileMemoryProvider.store failed for key %s: %s", key, e)
            return False

    def retrieve(self, key: str) -> dict | None:
        path = self._path_for(key)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error("FileMemoryProvider.retrieve failed for key %s: %s", key, e)
            return None

    def search(self, query: str, limit: int = 10) -> list[dict]:
        results: list[dict] = []
        q_lower = query.lower()
        for path in self._base_dir.glob("*.json"):
            if len(results) >= limit:
                break
            try:
                entry = json.loads(path.read_text(encoding="utf-8"))
                text = json.dumps(entry, ensure_ascii=False).lower()
                if q_lower in text:
                    results.append(entry)
            except Exception:
                continue
        return results

    def delete(self, key: str) -> bool:
        path = self._path_for(key)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_keys(self) -> list[str]:
        keys: list[str] = []
        for path in self._base_dir.glob("*.json"):
            keys.append(path.stem)
        return sorted(keys)


class InMemoryProvider(MemoryProvider):
    def __init__(self) -> None:
        self._store: dict[str, dict] = {}

    def store(self, key: str, entry: dict) -> bool:
        self._store[key] = entry
        return True

    def retrieve(self, key: str) -> dict | None:
        return self._store.get(key)

    def search(self, query: str, limit: int = 10) -> list[dict]:
        results: list[dict] = []
        q_lower = query.lower()
        for key, entry in self._store.items():
            if len(results) >= limit:
                break
            text = json.dumps(entry, ensure_ascii=False).lower()
            if q_lower in text:
                results.append(entry)
        return results

    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    def list_keys(self) -> list[str]:
        return sorted(self._store.keys())


def create_provider(provider_type: str = "file", **kwargs: Any) -> MemoryProvider:
    if provider_type == "file":
        base_dir = kwargs.get("base_dir", Path.home() / ".prometheus" / "memories")
        return FileMemoryProvider(base_dir=base_dir)
    elif provider_type == "memory":
        return InMemoryProvider()
    else:
        raise ValueError(f"Unknown provider type: {provider_type}")
