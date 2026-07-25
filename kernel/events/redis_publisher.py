from __future__ import annotations

import asyncio
import json
from typing import Any

from kernel.events.models import ExecutionEvent
from kernel.events.protocol import EventPublisher

try:
    import redis.asyncio as aioredis
    HAS_REDIS = True
except ImportError:
    aioredis = None  # type: ignore[assignment]
    HAS_REDIS = False


_SubscriberInfo = tuple[Any, str]  # (queue, tenant_id)


class RedisEventPublisher:
    """Redis-backed event publisher for distributed deployments.

    Publishes ExecutionEvents to Redis Pub/Sub channels and also
    delivers to local subscribers (same-process WebSocket clients).

    Channel pattern: {channel_prefix}:events:{execution_id}

    Requires the 'redis' package:
        pip install redis
    """

    def __init__(
        self,
        redis_url: str,
        channel_prefix: str = "kitematic",
    ) -> None:
        if not HAS_REDIS:
            raise RuntimeError(
                "Redis support requires the 'redis' package. "
                "Install it with: pip install redis"
            )
        self._redis_url = redis_url
        self._channel_prefix = channel_prefix
        self._redis: aioredis.Redis | None = None
        self._local_queues: dict[str, list[_SubscriberInfo]] = {}
        self._pubsub: aioredis.client.PubSub | None = None

    async def _ensure_connected(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
            )
        return self._redis

    async def publish(self, event: ExecutionEvent) -> None:
        channel = f"{self._channel_prefix}:events:{event.execution_id}"
        redis = await self._ensure_connected()
        data = json.dumps(event.to_dict())
        await redis.publish(channel, data)
        event_tenant = getattr(event, "tenant_id", "")
        for queue, sub_tenant in self._local_queues.get(event.execution_id, []):
            if sub_tenant and event_tenant and sub_tenant != event_tenant:
                continue
            queue.put_nowait(event.to_dict())

    def subscribe(self, execution_id: str, tenant_id: str = "") -> asyncio.Queue[Any]:
        from asyncio import Queue as _Queue
        queue: _Queue[Any] = _Queue()
        self._local_queues.setdefault(execution_id, []).append((queue, tenant_id))
        return queue

    def unsubscribe(self, execution_id: str, queue: asyncio.Queue[Any]) -> None:
        subs = self._local_queues.get(execution_id, [])
        self._local_queues[execution_id] = [
            (q, t) for q, t in subs if q is not queue
        ]

    def close(self, execution_id: str) -> None:
        for queue, _ in self._local_queues.get(execution_id, []):
            queue.put_nowait(None)
        self._local_queues.pop(execution_id, None)

    def close_all(self) -> None:
        for execution_id in list(self._local_queues.keys()):
            self.close(execution_id)

    @property
    def active_executions(self) -> list[str]:
        return list(self._local_queues.keys())

    def subscriber_count(self, execution_id: str) -> int:
        return len(self._local_queues.get(execution_id, []))


# Satisfy the protocol check if redis is available
if HAS_REDIS:
    _protocol_check = isinstance(RedisEventPublisher("redis://localhost"), EventPublisher)
