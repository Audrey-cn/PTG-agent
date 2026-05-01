from __future__ import annotations

import asyncio
from typing import Any, Callable, Coroutine, TypeVar

T = TypeVar("T")

DEFAULT_TIMEOUTS: dict[str, float] = {
    "api_call": 60.0,
    "tool_execution": 300.0,
    "model_response": 120.0,
    "file_operation": 30.0,
    "network_request": 30.0,
    "database_query": 60.0,
    "shell_command": 180.0,
    "startup": 30.0,
    "shutdown": 10.0,
    "health_check": 5.0,
    "authentication": 30.0,
    "session_load": 15.0,
    "session_save": 15.0,
    "checkpoint": 60.0,
    "memory_operation": 10.0,
}

_custom_timeouts: dict[str, float] = {}


def get_timeout(operation: str) -> float:
    if operation in _custom_timeouts:
        return _custom_timeouts[operation]
    return DEFAULT_TIMEOUTS.get(operation, 60.0)


def set_timeout(operation: str, seconds: float) -> None:
    _custom_timeouts[operation] = seconds


def reset_timeout(operation: str) -> None:
    if operation in _custom_timeouts:
        del _custom_timeouts[operation]


def reset_all_timeouts() -> None:
    _custom_timeouts.clear()


async def with_timeout(coro: Coroutine[Any, Any, T], operation: str) -> T:
    timeout = get_timeout(operation)
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        raise TimeoutError(f"Operation '{operation}' timed out after {timeout} seconds")


def with_timeout_sync(func: Callable[..., T], operation: str, *args, **kwargs) -> T:
    import signal
    
    timeout = get_timeout(operation)
    
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Operation '{operation}' timed out after {timeout} seconds")
    
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.setitimer(signal.ITIMER_REAL, timeout)
    
    try:
        result = func(*args, **kwargs)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
    
    return result
