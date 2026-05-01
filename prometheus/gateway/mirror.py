from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MirrorConfig:
    source_platform: str
    target_platforms: list[str] = field(default_factory=list)
    enabled: bool = True


class MessageMirror:
    def __init__(self) -> None:
        self._mirrors: dict[str, MirrorConfig] = {}
        self._lock = threading.Lock()

    def add_mirror(self, source_platform: str, target_platform: str) -> bool:
        with self._lock:
            if source_platform not in self._mirrors:
                self._mirrors[source_platform] = MirrorConfig(source_platform)
            mirror = self._mirrors[source_platform]
            if target_platform not in mirror.target_platforms:
                mirror.target_platforms.append(target_platform)
            return True

    def remove_mirror(self, source_platform: str) -> bool:
        with self._lock:
            if source_platform in self._mirrors:
                del self._mirrors[source_platform]
                return True
            return False

    def mirror_message(self, message: dict[str, Any], source: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        with self._lock:
            mirror = self._mirrors.get(source)
            if not mirror or not mirror.enabled:
                return results
            for target in mirror.target_platforms:
                mirrored = message.copy()
                mirrored["_mirrored_from"] = source
                mirrored["_mirrored_to"] = target
                results.append(mirrored)
        return results

    def list_mirrors(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "source_platform": m.source_platform,
                    "target_platforms": m.target_platforms.copy(),
                    "enabled": m.enabled,
                }
                for m in self._mirrors.values()
            ]
