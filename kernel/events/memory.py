from __future__ import annotations

import asyncio
from typing import Any

from kernel.events.models import ExecutionEvent
from kernel.events.protocol import EventPublisher

_SubscriberInfo = tuple[asyncio.Queue[Any], str]


class InMemoryEventPublisher:
    """In-memory event broker for WebSocket streaming.

    Each execution_id maps to a list of subscriber queues with tenant_id.
    publish() delivers to all subscribers for that execution, filtered by
    tenant_id when both event and subscriber have non-empty tenant_id.

    This is the default backend. Swap for RedisEventPublisher in production.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[_SubscriberInfo]] = {}

    def subscribe(self, execution_id: str, tenant_id: str = "") -> asyncio.Queue[Any]:
        queue: asyncio.Queue[Any] = asyncio.Queue()
        self._subscribers.setdefault(execution_id, []).append((queue, tenant_id))
        return queue

    def unsubscribe(self, execution_id: str, queue: asyncio.Queue[Any]) -> None:
        subs = self._subscribers.get(execution_id, [])
        self._subscribers[execution_id] = [
            (q, t) for q, t in subs if q is not queue
        ]

    async def publish(
        self,
        event_or_id: ExecutionEvent | str,
        event_dict: dict[str, Any] | None = None,
    ) -> None:
        if event_dict is not None:
            assert isinstance(event_or_id, str)  # noqa: S101
            execution_id: str = event_or_id
            for q, _ in self._subscribers.get(execution_id, []):
                q.put_nowait(event_dict)
        else:
            assert isinstance(event_or_id, ExecutionEvent)  # noqa: S101
            event: ExecutionEvent = event_or_id
            event_tenant = getattr(event, "tenant_id", "")
            for q, sub_tenant in self._subscribers.get(event.execution_id, []):
                if sub_tenant and event_tenant and sub_tenant != event_tenant:
                    continue
                q.put_nowait(event.to_dict())

    def close(self, execution_id: str) -> None:
        for queue, _ in self._subscribers.get(execution_id, []):
            queue.put_nowait(None)
        self._subscribers.pop(execution_id, None)

    def close_all(self) -> None:
        for execution_id in list(self._subscribers.keys()):
            self.close(execution_id)

    @property
    def active_executions(self) -> list[str]:
        return list(self._subscribers.keys())

    def subscriber_count(self, execution_id: str) -> int:
        return len(self._subscribers.get(execution_id, []))


# Satisfy the protocol check (runtime validation, not test assertion)
_protocol_check = isinstance(InMemoryEventPublisher(), EventPublisher)
