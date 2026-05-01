"""Generic slash-command confirmation primitive (gateway-side)."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

_pending: dict[str, dict[str, Any]] = {}
_lock = threading.RLock()

DEFAULT_TIMEOUT_SECONDS = 300


def register(
    session_key: str,
    confirm_id: str,
    command: str,
    handler: Callable[[str], Awaitable[str | None]],
) -> None:
    """Register a pending slash-command confirmation."""

    with _lock:
        _pending[session_key] = {
            "confirm_id": confirm_id,
            "command": command,
            "handler": handler,
            "created_at": time.time(),
        }


def get_pending(session_key: str) -> dict[str, Any] | None:
    """Return the pending confirm dict for a session, or None."""
    with _lock:
        entry = _pending.get(session_key)
        return dict(entry) if entry else None


def clear(session_key: str) -> None:
    """Drop the pending confirm for ``session_key`` without running it."""
    with _lock:
        _pending.pop(session_key, None)


def clear_if_stale(session_key: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> bool:
    """Drop the pending confirm if older than ``timeout`` seconds.

    Returns True if an entry was dropped.
    """
    with _lock:
        entry = _pending.get(session_key)
        if not entry:
            return False
        if time.time() - float(entry.get("created_at", 0) or 0) > timeout:
            _pending.pop(session_key, None)
            return True
        return False


async def resolve(
    session_key: str,
    confirm_id: str,
    choice: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str | None:
    """Resolve a pending confirm.

    ``choice`` must be one of ``"once"``, ``"always"``, or ``"cancel"``.
    Returns the handler's output string (to be sent as a follow-up
    message), or ``None`` if the confirm was stale, already resolved, or
    the confirm_id doesn't match.
    """
    with _lock:
        entry = _pending.get(session_key)
        if not entry:
            return None
        if entry.get("confirm_id") != confirm_id:
            return None
        _pending.pop(session_key, None)
        if time.time() - float(entry.get("created_at", 0) or 0) > timeout:
            return None
        handler = entry.get("handler")
        command = entry.get("command", "?")

    if not handler:
        return None
    try:
        result = await handler(choice)
    except Exception as exc:
        logger.error(
            "Slash-confirm handler for /%s raised: %s",
            command,
            exc,
            exc_info=True,
        )
        return f"❌ Error handling confirmation: {exc}"
    return result if isinstance(result, str) else None


def resolve_sync_compat(
    loop: asyncio.AbstractEventLoop,
    session_key: str,
    confirm_id: str,
    choice: str,
) -> str | None:
    """Synchronous helper: schedule resolve() on a loop and wait for the result."""

    try:
        fut = asyncio.run_coroutine_threadsafe(
            resolve(session_key, confirm_id, choice),
            loop,
        )
        return fut.result(timeout=30)
    except Exception as exc:
        logger.error("resolve_sync_compat failed: %s", exc)
        return None
