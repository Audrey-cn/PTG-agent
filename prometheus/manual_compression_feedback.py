from __future__ import annotations

from typing import Any


class CompressionFeedback:
    def __init__(self, context_compressor: Any = None):
        self._important_messages: Set[str] = set()
        self._context_compressor = context_compressor

    def mark_important(self, message_id: str) -> None:
        self._important_messages.add(message_id)

    def unmark_important(self, message_id: str) -> None:
        self._important_messages.discard(message_id)

    def get_important_messages(self) -> List[str]:
        return sorted(self._important_messages)

    def should_preserve(self, message_id: str) -> bool:
        return message_id in self._important_messages

    def get_preservation_count(self) -> int:
        return len(self._important_messages)

    def clear_all(self) -> None:
        self._important_messages.clear()

    def import_important(self, message_ids: List[str]) -> None:
        for mid in message_ids:
            self._important_messages.add(mid)

    def export_state(self) -> Dict[str, Any]:
        return {
            "important_messages": list(self._important_messages),
        }

    def import_state(self, state: Dict[str, Any]) -> None:
        self._important_messages = set(state.get("important_messages", []))
