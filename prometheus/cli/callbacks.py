from __future__ import annotations

import queue
import threading
from typing import Any, Callable, Dict, List, Optional


class CallbackManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._queues: Dict[str, queue.Queue] = {}
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
    
    def get_queue(self, session_id: str) -> Optional[queue.Queue]:
        return self._queues.get(session_id)
    
    def send(self, session_id: str, message: Dict[str, Any]):
        q = self.get_queue(session_id)
        if q:
            q.put(message)


callback_manager = CallbackManager()


def clarify_callback(
    cli: Any,
    question: str,
    choices: List[str],
    session_id: Optional[str] = None
) -> str:
    q = callback_manager.get_queue(session_id or "default")
    if q is None:
        if hasattr(cli, 'prompt'):
            return cli.prompt(question, choices=choices)
        return choices[0] if choices else ""
    
    response_event = threading.Event()
    response_holder: Dict[str, str] = {"value": ""}
    
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
    
    callback_manager.send(session_id or "default", {
        "type": "clarify_request",
        "question": question,
        "choices": choices
    })
    
    wait_for_response()
    response_event.wait(timeout=60)
    return response_holder["value"]


def approval_callback(
    cli: Any,
    command: str,
    risk_level: str = "medium",
    session_id: Optional[str] = None
) -> bool:
    q = callback_manager.get_queue(session_id or "default")
    if q is None:
        if hasattr(cli, 'confirm'):
            return cli.confirm(f"Approve command? [risk: {risk_level}]\n{command}")
        return True
    
    response_event = threading.Event()
    response_holder: Dict[str, bool] = {"value": True}
    
    def wait_for_response():
        while True:
            try:
                msg = q.get(timeout=120)
                if msg.get("type") == "approval_response":
                    response_holder["value"] = msg.get("approved", False)
                    response_event.set()
                    break
            except queue.Empty:
                response_holder["value"] = False
                response_event.set()
                break
    
    callback_manager.send(session_id or "default", {
        "type": "approval_request",
        "command": command,
        "risk_level": risk_level
    })
    
    wait_for_response()
    response_event.wait(timeout=120)
    return response_holder["value"]


def sudo_callback(
    cli: Any,
    command: str,
    session_id: Optional[str] = None
) -> str:
    q = callback_manager.get_queue(session_id or "default")
    if q is None:
        if hasattr(cli, 'prompt_secret'):
            return cli.prompt_secret(f"Sudo password required for: {command}")
        return ""
    
    response_event = threading.Event()
    response_holder: Dict[str, str] = {"value": ""}
    
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
    
    callback_manager.send(session_id or "default", {
        "type": "sudo_request",
        "command": command
    })
    
    wait_for_response()
    response_event.wait(timeout=60)
    return response_holder["value"]


def progress_callback(
    cli: Any,
    message: str,
    progress: float,
    session_id: Optional[str] = None
):
    q = callback_manager.get_queue(session_id or "default")
    
    progress_data = {
        "type": "progress",
        "message": message,
        "progress": min(1.0, max(0.0, progress))
    }
    
    if q is not None:
        callback_manager.send(session_id or "default", progress_data)
    
    if hasattr(cli, 'update_progress'):
        cli.update_progress(message, progress)


def register_callback_queue(session_id: str) -> queue.Queue:
    return callback_manager.register(session_id)


def unregister_callback_queue(session_id: str):
    callback_manager.unregister(session_id)


def send_callback_message(session_id: str, message: Dict[str, Any]):
    callback_manager.send(session_id, message)
