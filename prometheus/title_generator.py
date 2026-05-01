from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prometheus.auxiliary_client import AuxiliaryClient

logger = logging.getLogger(__name__)

_SANITIZE_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_SANITIZE_WHITESPACE = re.compile(r"\s+")
_MAX_TITLE_LEN = 80


class TitleGenerator:
    def __init__(self, auxiliary_client: AuxiliaryClient | None = None) -> None:
        self._client = auxiliary_client
        self._cache: Dict[str, str] = {}

    def generate(self, messages: list[Dict[str, str]]) -> str:
        cache_key = self._make_cache_key(messages)
        if cache_key in self._cache:
            return self._cache[cache_key]

        title = ""
        if self._client is not None:
            try:
                title = self._client.generate_title(messages)
            except Exception as e:
                logger.warning("TitleGenerator: auxiliary client failed: %s", e)

        if not title:
            title = self._extract_title(messages)

        title = self.sanitize(title)
        self._cache[cache_key] = title
        return title

    def sanitize(self, title: str) -> str:
        title = _SANITIZE_PATTERN.sub("", title)
        title = _SANITIZE_WHITESPACE.sub(" ", title).strip()
        if len(title) > _MAX_TITLE_LEN:
            title = title[:_MAX_TITLE_LEN].rsplit(" ", 1)[0]
        return title

    def _extract_title(self, messages: list[Dict[str, str]]) -> str:
        for msg in messages[:3]:
            if msg.get("role") == "user":
                content = msg.get("content", "").strip()
                if content:
                    first_line = content.split("\n")[0].strip()
                    if len(first_line) > 60:
                        return first_line[:57] + "..."
                    return first_line
        return "Untitled"

    def _make_cache_key(self, messages: list[Dict[str, str]]) -> str:
        parts: List[str] = []
        for msg in messages[:4]:
            role = msg.get("role", "")
            content = msg.get("content", "")[:100]
            parts.append(f"{role}:{content}")
        return "|".join(parts)
