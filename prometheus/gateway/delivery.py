from __future__ import annotations

import logging
from typing import Any

from prometheus.gateway.session import SessionManager

logger = logging.getLogger(__name__)

PLATFORM_LIMITS: dict[str, int] = {
    "telegram": 4096,
    "discord": 2000,
    "slack": 40000,
    "feishu": 4000,
    "dingtalk": 5000,
    "qqbot": 2000,
    "wecom": 2048,
    "cli": 100000,
}


class MessageDelivery:
    def __init__(self, session_manager: SessionManager):
        self._session_manager = session_manager
        self._adapters: dict[str, Any] = {}

    def register_adapter(self, platform: str, adapter: Any) -> None:
        self._adapters[platform] = adapter

    def unregister_adapter(self, platform: str) -> None:
        self._adapters.pop(platform, None)

    def _split_message(self, message: str, limit: int) -> list[str]:
        if len(message) <= limit:
            return [message]
        chunks: list[str] = []
        remaining = message
        while remaining:
            if len(remaining) <= limit:
                chunks.append(remaining)
                break
            split_at = remaining.rfind("\n", 0, limit)
            if split_at == -1:
                split_at = remaining.rfind(" ", 0, limit)
            if split_at == -1:
                split_at = limit
            chunks.append(remaining[:split_at])
            remaining = remaining[split_at:].lstrip("\n")
        return chunks

    async def send(self, platform: str, chat_id: str, message: str, **kwargs: Any) -> bool:
        adapter = self._adapters.get(platform)
        if not adapter:
            logger.error("No adapter registered for platform: %s", platform)
            return False
        limit = PLATFORM_LIMITS.get(platform, 4096)
        chunks = self._split_message(message, limit)
        success = True
        for chunk in chunks:
            try:
                result = await adapter.send(chat_id, chunk, **kwargs)
                if not result:
                    success = False
            except Exception as e:
                logger.error("Failed to send message to %s/%s: %s", platform, chat_id, e)
                success = False
        return success

    async def broadcast(self, message: str, platforms: list[str] | None = None) -> int:
        target_platforms = platforms or list(self._adapters.keys())
        sent_count = 0
        for platform in target_platforms:
            adapter = self._adapters.get(platform)
            if not adapter:
                continue
            try:
                chat_ids = await adapter.get_chat_ids()
                for chat_id in chat_ids:
                    result = await self.send(platform, chat_id, message)
                    if result:
                        sent_count += 1
            except Exception as e:
                logger.error("Broadcast failed for %s: %s", platform, e)
        return sent_count
