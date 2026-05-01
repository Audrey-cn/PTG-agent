from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from prometheus.config import get_prometheus_home


@dataclass
class ChannelMetadata:
    channel_id: str
    platform: str
    name: str = ""
    description: str = ""
    created_at: float = 0.0
    tags: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)


class ChannelDirectory:
    def __init__(self, persist: bool = False) -> None:
        self._channels: dict[str, ChannelMetadata] = {}
        self._persist = persist
        self._lock = threading.Lock()
        if persist:
            self._load_from_disk()

    def _storage_path(self) -> Path:
        return get_prometheus_home() / "channel_directory.json"

    def _load_from_disk(self) -> None:
        path = self._storage_path()
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("channels", []):
                    channel = ChannelMetadata(
                        channel_id=item["channel_id"],
                        platform=item.get("platform", ""),
                        name=item.get("name", ""),
                        description=item.get("description", ""),
                        created_at=item.get("created_at", 0.0),
                        tags=item.get("tags", []),
                        config=item.get("config", {}),
                    )
                    self._channels[channel.channel_id] = channel
            except Exception:
                pass

    def _save_to_disk(self) -> None:
        if not self._persist:
            return
        path = self._storage_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "channels": [
                {
                    "channel_id": c.channel_id,
                    "platform": c.platform,
                    "name": c.name,
                    "description": c.description,
                    "created_at": c.created_at,
                    "tags": c.tags,
                    "config": c.config,
                }
                for c in self._channels.values()
            ]
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def register_channel(self, channel_id: str, metadata: dict[str, Any]) -> bool:
        import time
        with self._lock:
            if channel_id in self._channels:
                return False
            channel = ChannelMetadata(
                channel_id=channel_id,
                platform=metadata.get("platform", ""),
                name=metadata.get("name", ""),
                description=metadata.get("description", ""),
                created_at=metadata.get("created_at", time.time()),
                tags=metadata.get("tags", []),
                config=metadata.get("config", {}),
            )
            self._channels[channel_id] = channel
            self._save_to_disk()
            return True

    def unregister_channel(self, channel_id: str) -> bool:
        with self._lock:
            if channel_id in self._channels:
                del self._channels[channel_id]
                self._save_to_disk()
                return True
            return False

    def get_channel(self, channel_id: str) -> dict[str, Any] | None:
        with self._lock:
            channel = self._channels.get(channel_id)
            if channel:
                return {
                    "channel_id": channel.channel_id,
                    "platform": channel.platform,
                    "name": channel.name,
                    "description": channel.description,
                    "created_at": channel.created_at,
                    "tags": channel.tags.copy(),
                    "config": channel.config.copy(),
                }
            return None

    def list_channels(self, platform: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            channels = []
            for c in self._channels.values():
                if platform is None or c.platform == platform:
                    channels.append({
                        "channel_id": c.channel_id,
                        "platform": c.platform,
                        "name": c.name,
                        "description": c.description,
                        "created_at": c.created_at,
                        "tags": c.tags.copy(),
                        "config": c.config.copy(),
                    })
            return channels

    def find_channel(self, query: str) -> list[dict[str, Any]]:
        with self._lock:
            results = []
            query_lower = query.lower()
            for c in self._channels.values():
                if (
                    query_lower in c.channel_id.lower()
                    or query_lower in c.name.lower()
                    or query_lower in c.description.lower()
                    or any(query_lower in tag.lower() for tag in c.tags)
                ):
                    results.append({
                        "channel_id": c.channel_id,
                        "platform": c.platform,
                        "name": c.name,
                        "description": c.description,
                        "created_at": c.created_at,
                        "tags": c.tags.copy(),
                        "config": c.config.copy(),
                    })
            return results
