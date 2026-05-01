from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("prometheus.acp_adapter.events")

EVENT_TYPES = {
    "tool_call",
    "message",
    "error",
    "state_change"
}


@dataclass
class Event:
    event_type: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


class ACPEvents:
    def __init__(self, max_history: int = 100) -> None:
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._history: Dict[str, List[Event]] = defaultdict(list)
        self._max_history = max_history

    def subscribe(self, event_type: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        if event_type not in EVENT_TYPES:
            logger.warning(f"Unknown event type: {event_type}")

        self._subscribers[event_type].append(callback)
        logger.debug(f"Subscribed to event: {event_type}")

    def unsubscribe(self, event_type: str, callback: Callable[[Dict[str, Any]], None]) -> bool:
        if event_type not in self._subscribers:
            return False

        if callback in self._subscribers[event_type]:
            self._subscribers[event_type].remove(callback)
            logger.debug(f"Unsubscribed from event: {event_type}")
            return True

        return False

    def emit(self, event_type: str, data: Dict[str, Any]) -> None:
        if event_type not in EVENT_TYPES:
            logger.warning(f"Unknown event type: {event_type}")

        event = Event(event_type=event_type, data=data)

        self._history[event_type].append(event)
        if len(self._history[event_type]) > self._max_history:
            self._history[event_type] = self._history[event_type][-self._max_history:]

        for callback in self._subscribers[event_type]:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Event callback failed: {e}")

        logger.debug(f"Emitted event: {event_type}")

    def get_event_history(self, event_type: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if event_type not in self._history:
            return []

        history = self._history[event_type]
        if limit:
            history = history[-limit:]

        return [
            {
                "event_type": e.event_type,
                "data": e.data,
                "timestamp": e.timestamp.isoformat()
            }
            for e in history
        ]

    def clear_history(self, event_type: Optional[str] = None) -> None:
        if event_type:
            self._history[event_type] = []
        else:
            self._history.clear()
        logger.debug(f"Cleared event history: {event_type or 'all'}")

    def get_subscriber_count(self, event_type: str) -> int:
        return len(self._subscribers.get(event_type, []))

    def list_event_types(self) -> List[str]:
        return list(EVENT_TYPES)
