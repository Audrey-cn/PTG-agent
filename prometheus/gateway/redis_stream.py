from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class StreamMessage:
    id: str
    stream: str
    data: dict[str, Any]
    timestamp: float


@dataclass
class Subscription:
    stream: str
    callback: Callable[[StreamMessage], None]
    active: bool = True


class RedisStreamBackend:
    def __init__(self) -> None:
        self._connected = False
        self._redis_client: Any = None
        self._url: str = ""
        self._in_memory_streams: dict[str, list[StreamMessage]] = {}
        self._subscriptions: dict[str, list[Subscription]] = {}
        self._lock = threading.Lock()
        self._message_counter = 0

    def connect(self, url: str) -> bool:
        self._url = url
        try:
            import redis
            self._redis_client = redis.from_url(url)
            self._redis_client.ping()
            self._connected = True
            return True
        except Exception:
            self._connected = False
            self._redis_client = None
            return False

    def _generate_message_id(self) -> str:
        with self._lock:
            self._message_counter += 1
            return f"{int(time.time() * 1000)}-{self._message_counter}"

    def publish(self, stream: str, message: dict[str, Any]) -> str:
        msg_id = self._generate_message_id()
        msg = StreamMessage(
            id=msg_id,
            stream=stream,
            data=message,
            timestamp=time.time(),
        )
        if self._connected and self._redis_client:
            try:
                self._redis_client.xadd(stream, {"data": json.dumps(message)})
            except Exception:
                pass
        with self._lock:
            if stream not in self._in_memory_streams:
                self._in_memory_streams[stream] = []
            self._in_memory_streams[stream].append(msg)
        self._notify_subscribers(stream, msg)
        return msg_id

    def _notify_subscribers(self, stream: str, message: StreamMessage) -> None:
        with self._lock:
            subs = self._subscriptions.get(stream, [])
        for sub in subs:
            if sub.active:
                try:
                    sub.callback(message)
                except Exception:
                    pass

    def subscribe(self, stream: str, callback: Callable[[StreamMessage], None]) -> str:
        import uuid
        sub_id = str(uuid.uuid4())
        sub = Subscription(stream=stream, callback=callback)
        with self._lock:
            if stream not in self._subscriptions:
                self._subscriptions[stream] = []
            self._subscriptions[stream].append(sub)
        if self._connected and self._redis_client:
            pass
        return sub_id

    def unsubscribe(self, stream: str) -> bool:
        with self._lock:
            if stream in self._subscriptions:
                for sub in self._subscriptions[stream]:
                    sub.active = False
                del self._subscriptions[stream]
                return True
            return False

    def get_messages(self, stream: str, count: int = 10) -> list[dict[str, Any]]:
        with self._lock:
            messages = self._in_memory_streams.get(stream, [])[-count:]
            return [
                {
                    "id": m.id,
                    "stream": m.stream,
                    "data": m.data,
                    "timestamp": m.timestamp,
                }
                for m in messages
            ]

    def is_connected(self) -> bool:
        return self._connected

    def disconnect(self) -> None:
        if self._redis_client:
            try:
                self._redis_client.close()
            except Exception:
                pass
        self._connected = False
        self._redis_client = None
