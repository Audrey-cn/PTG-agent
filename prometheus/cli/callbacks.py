from __future__ import annotations

import queue
import threading
from typing import Any


class CallbackManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._queues: dict[str, queue.Queue] = {}
            cls._instance._lock = threading.Lock()
        return cls._instance

    def register(self, session_id: str) -> queue.Queue:
        with self._lock:
            if session_id not in self._queues:
                self._queues[session_id] = queue.Queue()
            return self._queues[session_id]

    def unregister(self, session_id: str):
        with self._lock:
            if session_id in self._queues:
                del self._queues[session_id]

    def get_queue(self, session_id: str) -> queue.Queue | None:
        return self._queues.get(session_id)

    def send(self, session_id: str, message: dict[str, Any]):
        q = self.get_queue(session_id)
        if q:
            q.put(message)


callback_manager = CallbackManager()


def clarify_callback(
    cli: Any, question: str, choices: list[str], session_id: str | None = None
) -> str:
    q = callback_manager.get_queue(session_id or "default")
    if q is None:
        if hasattr(cli, "prompt"):
            return cli.prompt(question, choices=choices)
        return choices[0] if choices else ""

    response_event = threading.Event()
    response_holder: dict[str, str] = {"value": ""}

    def wait_for_response():
        while True:
            try:
                msg = q.get(timeout=60)
                if msg.get("type") == "clarify_response":
                    response_holder["value"] = msg.get("choice", "")
                    response_event.set()
                    break
            except queue.Empty:
                response_holder["value"] = choices[0] if choices else ""
                response_event.set()
                break

    callback_manager.send(
        session_id or "default",
        {"type": "clarify_request", "question": question, "choices": choices},
    )

    wait_for_response()
    response_event.wait(timeout=60)
    return response_holder["value"]


def approval_callback(
    cli: Any,
    command: str,
    description: str,
    *,
    allow_permanent: bool = True,
) -> str:
    """Prompt for dangerous command approval through the TUI.

    Mirrors Prometheus's approval_callback interface for compatibility.

    Shows a selection UI with choices: once / session / always / deny.
    When the command is longer than 70 characters, a "view" option is
    included so the user can reveal the full text before deciding.

    Uses cli._approval_lock to serialize concurrent requests (e.g. from
    parallel delegation subtasks) so each prompt gets its own turn.

    Args:
        cli: The CLI instance
        command: The dangerous command to approve
        description: Human-readable description of why it's dangerous
        allow_permanent: When False, hide the [a]lways option

    Returns:
        'once', 'session', 'always', or 'deny'
    """
    import time as _time

    lock = getattr(cli, "_approval_lock", None)
    if lock is None:
        cli._approval_lock = threading.Lock()
        lock = cli._approval_lock

    with lock:
        try:
            from prometheus.tools.config import get_config

            config = get_config()
            timeout = config.get("approvals.timeout", 60)
        except Exception:
            timeout = 60

        response_queue = queue.Queue()
        choices = ["once", "session", "always", "deny"]
        if len(command) > 70:
            choices.append("view")

        cli._approval_state = {
            "command": command,
            "description": description,
            "choices": choices,
            "selected": 0,
            "response_queue": response_queue,
        }
        cli._approval_deadline = _time.monotonic() + timeout

        if hasattr(cli, "_app") and cli._app:
            cli._app.invalidate()

        while True:
            try:
                result = response_queue.get(timeout=1)
                cli._approval_state = None
                cli._approval_deadline = 0
                if hasattr(cli, "_app") and cli._app:
                    cli._app.invalidate()
                return result
            except queue.Empty:
                if _time.monotonic() >= cli._approval_deadline:
                    cli._approval_state = None
                    cli._approval_deadline = 0
                    if hasattr(cli, "_app") and cli._app:
                        cli._app.invalidate()
                    return "deny"
            except Exception:
                return "deny"


def sudo_callback(cli: Any, command: str, session_id: str | None = None) -> str:
    """Prompt for sudo password through the TUI or queue.

    Args:
        cli: The CLI instance
        command: The command requiring sudo
        session_id: Optional session ID for queue-based responses

    Returns:
        The sudo password, or empty string if cancelled/timeout
    """
    q = callback_manager.get_queue(session_id or "default")
    if q is None:
        if hasattr(cli, "prompt_secret"):
            return cli.prompt_secret(f"Sudo password required for: {command}")
        return ""

    response_event = threading.Event()
    response_holder: dict[str, str] = {"value": ""}

    def wait_for_response():
        while True:
            try:
                msg = q.get(timeout=60)
                if msg.get("type") == "sudo_response":
                    response_holder["value"] = msg.get("password", "")
                    response_event.set()
                    break
            except queue.Empty:
                response_holder["value"] = ""
                response_event.set()
                break

    callback_manager.send(session_id or "default", {"type": "sudo_request", "command": command})

    wait_for_response()
    response_event.wait(timeout=60)
    return response_holder["value"]


def progress_callback(cli: Any, message: str, progress: float, session_id: str | None = None):
    q = callback_manager.get_queue(session_id or "default")

    progress_data = {
        "type": "progress",
        "message": message,
        "progress": min(1.0, max(0.0, progress)),
    }

    if q is not None:
        callback_manager.send(session_id or "default", progress_data)

    if hasattr(cli, "update_progress"):
        cli.update_progress(message, progress)


def register_callback_queue(session_id: str) -> queue.Queue:
    return callback_manager.register(session_id)


def unregister_callback_queue(session_id: str):
    callback_manager.unregister(session_id)


def send_callback_message(session_id: str, message: dict[str, Any]):
    callback_manager.send(session_id, message)
