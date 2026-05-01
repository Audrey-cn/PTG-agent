"""Per-thread interrupt signaling for all tools."""

import logging
import os
import threading

logger = logging.getLogger(__name__)

_DEBUG_INTERRUPT = bool(os.getenv("PROMETHEUS_DEBUG_INTERRUPT"))

if _DEBUG_INTERRUPT:
    logger.setLevel(logging.INFO)

_interrupted_threads: Set[int] = set()
_lock = threading.Lock()


def set_interrupt(active: bool, thread_id: int | None = None) -> None:
    """Set or clear interrupt for a specific thread."""

    tid = thread_id if thread_id is not None else threading.current_thread().ident
    with _lock:
        if active:
            _interrupted_threads.add(tid)
        else:
            _interrupted_threads.discard(tid)
        _snapshot = set(_interrupted_threads) if _DEBUG_INTERRUPT else None
    if _DEBUG_INTERRUPT:
        logger.info(
            "[interrupt-debug] set_interrupt(active=%s, target_tid=%s) "
            "called_from_tid=%s current_set=%s",
            active,
            tid,
            threading.current_thread().ident,
            _snapshot,
        )


def is_interrupted() -> bool:
    """Check if an interrupt has been requested for the current thread."""

    tid = threading.current_thread().ident
    with _lock:
        return tid in _interrupted_threads


class _ThreadAwareEventProxy:
    """Drop-in proxy that maps threading.Event methods to per-thread state."""

    def is_set(self) -> bool:
        return is_interrupted()

    def set(self) -> None:
        set_interrupt(True)

    def clear(self) -> None:
        set_interrupt(False)

    def wait(self, timeout: float | None = None) -> bool:
        return self.is_set()


_interrupt_event = _ThreadAwareEventProxy()
