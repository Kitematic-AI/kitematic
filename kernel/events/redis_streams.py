"""Redis Streams event publisher for production event infrastructure.

Replaces basic Redis Pub/Sub with Redis Streams, providing:
  - At-least-once delivery via consumer groups
  - Tenant-isolated consumer groups
  - Replay capability (XREAD from any point in time)
  - Message acknowledgment
  - Backward-compatible with EventPublisher protocol

Requires:
    pip install redis
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from kernel.events.models import ExecutionEvent
from kernel.events.protocol import EventPublisher

try:
    import redis.asyncio as aioredis
    HAS_REDIS = True
except ImportError:
    aioredis = None  # type: ignore[assignment]
    HAS_REDIS = False

MIN_IDLE_MS = 60000

_SubscriberInfo = tuple[asyncio.Queue[Any], str]


class RedisStreamPublisher:
    """Redis Streams-backed event publisher.

    Publishes ExecutionEvents via XADD to tenant-partitioned streams.
    Consumer groups are created per tenant for horizontal scaling.

    Stream key format:  {prefix}:s:{execution_id}
    Consumer group:     {prefix}:g:{tenant_id}
    Consumer name:      {prefix}:c:{instance_id}
    """

    def __init__(
        self,
        redis_url: str,
        stream_prefix: str = "kitematic",
        instance_id: str = "",
    ) -> None:
        if not HAS_REDIS:
            raise RuntimeError(
                "Redis Streams support requires the 'redis' package. "
                "Install it with: pip install redis"
            )
        self._redis_url = redis_url
        self._prefix = stream_prefix
        self._instance_id = instance_id or f"inst-{id(self):x}"
        self._redis: aioredis.Redis | None = None
        self._local_queues: dict[str, list[_SubscriberInfo]] = {}
        self._stream_keys: set[str] = set()

    async def _ensure_connected(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
            )
        return self._redis

    def _stream_key(self, execution_id: str) -> str:
        return f"{self._prefix}:s:{execution_id}"

    def _group_name(self, tenant_id: str) -> str:
        return f"{self._prefix}:g:{tenant_id or 'default'}"

    def _consumer_name(self) -> str:
        return f"{self._prefix}:c:{self._instance_id}"

    async def publish(self, event: ExecutionEvent) -> None:
        stream = self._stream_key(event.execution_id)
        redis = await self._ensure_connected()
        data = event.to_dict()
        et = event.event_type
        data["__event_type__"] = et.value if hasattr(et, "value") else str(et)
        data["__tenant_id__"] = event.tenant_id or ""
        data["__agent_id__"] = event.agent_id or ""
        data["__timestamp__"] = str(time.time())
        await redis.xadd(stream, data, maxlen=10000)  # type: ignore[arg-type]
        self._stream_keys.add(stream)
        event_tenant = event.tenant_id or ""
        for queue, sub_tenant in self._local_queues.get(event.execution_id, []):
            if sub_tenant and event_tenant and sub_tenant != event_tenant:
                continue
            queue.put_nowait(data)

    def subscribe(self, execution_id: str, tenant_id: str = "") -> asyncio.Queue[Any]:
        queue: asyncio.Queue[Any] = asyncio.Queue()
        self._local_queues.setdefault(execution_id, []).append((queue, tenant_id))
        return queue

    def unsubscribe(self, execution_id: str, queue: asyncio.Queue[Any]) -> None:
        subs = self._local_queues.get(execution_id, [])
        self._local_queues[execution_id] = [
            (q, t) for q, t in subs if q is not queue
        ]

    def close(self, execution_id: str) -> None:
        stream = self._stream_key(execution_id)
        self._stream_keys.discard(stream)
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

    async def ensure_consumer_group(self, tenant_id: str = "") -> str:
        """Create or reuse a consumer group for a tenant.

        Returns the group name.
        """
        redis = await self._ensure_connected()
        group = self._group_name(tenant_id)
        for stream in list(self._stream_keys):
            try:
                await redis.xgroup_create(
                    stream,
                    group,
                    id="0",
                    mkstream=True,
                )
            except aioredis.ResponseError as e:
                if "BUSYGROUP" not in str(e):
                    raise
        return group

    async def read_messages(
        self,
        tenant_id: str = "",
        count: int = 10,
        block_ms: int = 5000,
    ) -> list[dict[str, Any]]:
        """Read pending messages from the tenant's consumer group.

        Returns a list of parsed event dicts (without stream metadata).
        """
        redis = await self._ensure_connected()
        group = self._group_name(tenant_id)
        consumer = self._consumer_name()

        if self._stream_keys:
            stream_keys = list(self._stream_keys)
        else:
            stream_keys = [f"{self._prefix}:s:placeholder"]
        if not stream_keys:
            return []

        try:
            results = await redis.xreadgroup(
                group,
                consumer,
                {stream: ">" for stream in stream_keys},
                count=count,
                block=block_ms,
            )
        except aioredis.ResponseError:
            return []

        messages: list[dict[str, Any]] = []
        if results is None:
            return messages
        for result_item in results:
            if not isinstance(result_item, (list, tuple)) or len(result_item) != 2:
                continue
            stream_name, entries = result_item
            if stream_name is None:
                continue
            stream = str(stream_name)
            if entries is None:
                continue
            for msg_id, fields in entries:
                messages.append({"stream": stream, "id": str(msg_id), "data": fields})
        return messages

    async def acknowledge(self, stream: str, msg_id: str, tenant_id: str = "") -> None:
        """Acknowledge a message after successful processing."""
        redis = await self._ensure_connected()
        group = self._group_name(tenant_id)
        await redis.xack(stream, group, msg_id)

    async def replay(
        self,
        execution_id: str,
        tenant_id: str = "",
        start_id: str = "0",
        count: int = 100,
    ) -> list[dict[str, Any]]:
        """Replay messages from a stream (for recovery on reconnect).

        Uses XRANGE to read from a stream without consumer groups.
        """
        redis = await self._ensure_connected()
        stream = self._stream_key(execution_id)
        try:
            entries = await redis.xrange(stream, min=start_id, max="+", count=count)
        except aioredis.ResponseError:
            return []
        if entries is None:
            return []
        return [
            {"stream": stream, "id": str(msg_id), "data": fields}
            for msg_id, fields in (entries or [])
        ]

    async def trim(self, execution_id: str, maxlen: int = 10000) -> None:
        """Trim a stream to prevent unbounded growth."""
        redis = await self._ensure_connected()
        stream = self._stream_key(execution_id)
        try:
            await redis.xtrim(stream, maxlen=maxlen)
        except aioredis.ResponseError:
            pass


if HAS_REDIS:
    _protocol_check = isinstance(RedisStreamPublisher("redis://localhost"), EventPublisher)
