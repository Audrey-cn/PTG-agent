from __future__ import annotations

import asyncio
import json
import threading
from collections import defaultdict
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


class StreamConsumer:
    def __init__(self, use_redis: bool = False, redis_url: str = "redis://localhost:6379"):
        self._use_redis = use_redis
        self._redis_url = redis_url
        self._redis_client = None
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._streams: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._running = False
        self._consumer_task: asyncio.Task | None = None
        self._lock = threading.Lock()

    def _check_redis(self) -> bool:
        if not self._use_redis:
            return False
        try:
            import redis.asyncio as aioredis

            return True
        except ImportError:
            return False

    async def _init_redis(self):
        if self._use_redis and self._check_redis():
            import redis.asyncio as aioredis

            self._redis_client = await aioredis.from_url(self._redis_url)

    async def _close_redis(self):
        if self._redis_client:
            await self._redis_client.close()
            self._redis_client = None

    def subscribe(self, stream_name: str, callback: Callable[[dict[str, Any]], None]):
        with self._lock:
            if callback not in self._subscribers[stream_name]:
                self._subscribers[stream_name].append(callback)

    def unsubscribe(self, stream_name: str, callback: Callable | None = None):
        with self._lock:
            if callback:
                if callback in self._subscribers[stream_name]:
                    self._subscribers[stream_name].remove(callback)
            else:
                self._subscribers[stream_name] = []

    async def _consume_memory_stream(self, stream_name: str):
        while self._running:
            try:
                messages = self._streams.get(stream_name, [])
                while messages:
                    msg = messages.pop(0)
                    for callback in self._subscribers.get(stream_name, []):
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(msg)
                            else:
                                callback(msg)
                        except Exception:
                            pass
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break

    async def _consume_redis_stream(self, stream_name: str):
        if not self._redis_client:
            return

        last_id = "0"
        while self._running:
            try:
                results = await self._redis_client.xread(
                    {stream_name: last_id}, count=10, block=1000
                )
                if results:
                    for _stream, messages in results:
                        for msg_id, msg_data in messages:
                            last_id = msg_id.decode() if isinstance(msg_id, bytes) else msg_id
                            decoded_data = {}
                            for k, v in msg_data.items():
                                key = k.decode() if isinstance(k, bytes) else k
                                val = v.decode() if isinstance(v, bytes) else v
                                try:
                                    decoded_data[key] = json.loads(val)
                                except (json.JSONDecodeError, TypeError):
                                    decoded_data[key] = val

                            for callback in self._subscribers.get(stream_name, []):
                                try:
                                    if asyncio.iscoroutinefunction(callback):
                                        await callback(decoded_data)
                                    else:
                                        callback(decoded_data)
                                except Exception:
                                    pass
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1)

    async def start(self):
        self._running = True
        if self._use_redis and self._check_redis():
            await self._init_redis()

        tasks = []
        for stream_name in self._subscribers:
            if self._use_redis and self._redis_client:
                task = asyncio.create_task(self._consume_redis_stream(stream_name))
            else:
                task = asyncio.create_task(self._consume_memory_stream(stream_name))
            tasks.append(task)

        self._consumer_tasks = tasks

    async def stop(self):
        self._running = False
        for task in getattr(self, "_consumer_tasks", []):
            task.cancel()
        if self._redis_client:
            await self._close_redis()

    def publish(self, stream_name: str, message: dict[str, Any]):
        if self._use_redis and self._redis_client:
            asyncio.create_task(self._publish_redis(stream_name, message))
        else:
            self._streams[stream_name].append(message)

    async def _publish_redis(self, stream_name: str, message: dict[str, Any]):
        if not self._redis_client:
            return
        try:
            msg_data = {}
            for k, v in message.items():
                if isinstance(v, (dict, list)):
                    msg_data[k] = json.dumps(v)
                else:
                    msg_data[k] = str(v)
            await self._redis_client.xadd(stream_name, msg_data)
        except Exception:
            pass

    def get_pending_count(self, stream_name: str) -> int:
        return len(self._streams.get(stream_name, []))

    def get_subscriber_count(self, stream_name: str) -> int:
        return len(self._subscribers.get(stream_name, []))

    def list_streams(self) -> list[str]:
        return list(set(list(self._subscribers.keys()) + list(self._streams.keys())))


stream_consumer = StreamConsumer()
