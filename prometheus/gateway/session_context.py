"""Session-scoped context variables for the Prometheus gateway."""

from contextvars import ContextVar
from typing import Any

_UNSET: Any = object()

_SESSION_PLATFORM: ContextVar = ContextVar("PROMETHEUS_SESSION_PLATFORM", default=_UNSET)
_SESSION_CHAT_ID: ContextVar = ContextVar("PROMETHEUS_SESSION_CHAT_ID", default=_UNSET)
_SESSION_CHAT_NAME: ContextVar = ContextVar("PROMETHEUS_SESSION_CHAT_NAME", default=_UNSET)
_SESSION_THREAD_ID: ContextVar = ContextVar("PROMETHEUS_SESSION_THREAD_ID", default=_UNSET)
_SESSION_USER_ID: ContextVar = ContextVar("PROMETHEUS_SESSION_USER_ID", default=_UNSET)
_SESSION_USER_NAME: ContextVar = ContextVar("PROMETHEUS_SESSION_USER_NAME", default=_UNSET)
_SESSION_KEY: ContextVar = ContextVar("PROMETHEUS_SESSION_KEY", default=_UNSET)

_CRON_AUTO_DELIVER_PLATFORM: ContextVar = ContextVar(
    "PROMETHEUS_CRON_AUTO_DELIVER_PLATFORM", default=_UNSET
)
_CRON_AUTO_DELIVER_CHAT_ID: ContextVar = ContextVar(
    "PROMETHEUS_CRON_AUTO_DELIVER_CHAT_ID", default=_UNSET
)
_CRON_AUTO_DELIVER_THREAD_ID: ContextVar = ContextVar(
    "PROMETHEUS_CRON_AUTO_DELIVER_THREAD_ID", default=_UNSET
)

_VAR_MAP = {
    "PROMETHEUS_SESSION_PLATFORM": _SESSION_PLATFORM,
    "PROMETHEUS_SESSION_CHAT_ID": _SESSION_CHAT_ID,
    "PROMETHEUS_SESSION_CHAT_NAME": _SESSION_CHAT_NAME,
    "PROMETHEUS_SESSION_THREAD_ID": _SESSION_THREAD_ID,
    "PROMETHEUS_SESSION_USER_ID": _SESSION_USER_ID,
    "PROMETHEUS_SESSION_USER_NAME": _SESSION_USER_NAME,
    "PROMETHEUS_SESSION_KEY": _SESSION_KEY,
    "PROMETHEUS_CRON_AUTO_DELIVER_PLATFORM": _CRON_AUTO_DELIVER_PLATFORM,
    "PROMETHEUS_CRON_AUTO_DELIVER_CHAT_ID": _CRON_AUTO_DELIVER_CHAT_ID,
    "PROMETHEUS_CRON_AUTO_DELIVER_THREAD_ID": _CRON_AUTO_DELIVER_THREAD_ID,
}


def set_session_vars(
    platform: str = "",
    chat_id: str = "",
    chat_name: str = "",
    thread_id: str = "",
    user_id: str = "",
    user_name: str = "",
    session_key: str = "",
) -> list:
    """Set all session context variables and return reset tokens.

    Call ``clear_session_vars(tokens)`` in a ``finally`` block to restore
    the previous values when the handler exits.

    Returns a list of ``Token`` objects (one per variable) that can be
    passed to ``clear_session_vars``.
    """
    tokens = [
        _SESSION_PLATFORM.set(platform),
        _SESSION_CHAT_ID.set(chat_id),
        _SESSION_CHAT_NAME.set(chat_name),
        _SESSION_THREAD_ID.set(thread_id),
        _SESSION_USER_ID.set(user_id),
        _SESSION_USER_NAME.set(user_name),
        _SESSION_KEY.set(session_key),
    ]
    return tokens


def clear_session_vars(tokens: list) -> None:
    """Mark session context variables as explicitly cleared.

    Sets all variables to ``""`` so that ``get_session_env`` returns an empty
    string instead of falling back to (potentially stale) ``os.environ``
    values.  The *tokens* argument is accepted for API compatibility with
    callers that saved the return value of ``set_session_vars``, but the
    actual clearing uses ``var.set("")`` rather than ``var.reset(token)``
    to ensure the "explicitly cleared" state is distinguishable from
    "never set" (which holds the ``_UNSET`` sentinel).
    """
    for var in (
        _SESSION_PLATFORM,
        _SESSION_CHAT_ID,
        _SESSION_CHAT_NAME,
        _SESSION_THREAD_ID,
        _SESSION_USER_ID,
        _SESSION_USER_NAME,
        _SESSION_KEY,
    ):
        var.set("")


def get_session_env(name: str, default: str = "") -> str:
    """Read a session context variable by its legacy ``PROMETHEUS_SESSION_*`` name.

    Drop-in replacement for ``os.getenv("PROMETHEUS_SESSION_*", default)``.

    Resolution order:
    1. Context variable (set by the gateway for concurrency-safe access).
       If the variable was explicitly set (even to ``""``) via
       ``set_session_vars`` or ``clear_session_vars``, that value is
       returned — **no fallback to os.environ**.
    2. ``os.environ`` (only when the context variable was never set in
       this context — i.e. CLI, cron scheduler, and test processes that
       don't use ``set_session_vars`` at all).
    3. *default*
    """
    import os

    var = _VAR_MAP.get(name)
    if var is not None:
        value = var.get()
        if value is not _UNSET:
            return value
    return os.getenv(name, default)
