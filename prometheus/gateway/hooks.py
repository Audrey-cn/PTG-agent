from __future__ import annotations

import asyncio
from enum import Enum
from typing import Any, Callable, Coroutine


class HookType(Enum):
    PRE_SEND = "pre_send"
    POST_RECEIVE = "post_receive"
    PRE_PROCESS = "pre_process"
    POST_PROCESS = "post_process"
    ON_ERROR = "on_error"


HookCallback = Callable[..., Coroutine[Any, Any, Any]]


class _HookEntry:
    def __init__(self, callback: HookCallback, priority: int):
        self.callback = callback
        self.priority = priority

    def __lt__(self, other: _HookEntry) -> bool:
        return self.priority < other.priority


class HookManager:
    def __init__(self) -> None:
        self._hooks: dict[HookType, list[_HookEntry]] = {}

    def register(self, hook_type: HookType, callback: HookCallback, priority: int = 0) -> None:
        if hook_type not in self._hooks:
            self._hooks[hook_type] = []
        entry = _HookEntry(callback, priority)
        self._hooks[hook_type].append(entry)
        self._hooks[hook_type].sort()

    def unregister(self, hook_type: HookType, callback: HookCallback) -> None:
        if hook_type not in self._hooks:
            return
        self._hooks[hook_type] = [
            e for e in self._hooks[hook_type] if e.callback is not callback
        ]

    async def fire(self, hook_type: HookType, data: Any) -> Any:
        if hook_type not in self._hooks:
            return data
        for entry in self._hooks[hook_type]:
            try:
                result = await entry.callback(data)
                if result is not None:
                    data = result
            except Exception:
                pass
        return data
