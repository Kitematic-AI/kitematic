from __future__ import annotations

import asyncio
from typing import Any, Protocol, runtime_checkable

from runtime.kitematic_runtime.events.models import ExecutionEvent


@runtime_checkable
class EventPublisher(Protocol):
    """Protocol for event publishers.

    Runtime and API depend only on this protocol — they never know
    whether events are delivered via in-memory queues or Redis Pub/Sub.

    All implementations must handle:
      - publish: deliver ExecutionEvent to subscribers
      - subscribe: register a queue for an execution
      - unsubscribe: remove a queue
      - close: end event stream for a single execution
      - close_all: end all event streams
      - active_executions: list executions with subscribers
      - subscriber_count: count of active subscribers

    Tenant isolation:
      subscribe() requires tenant_id for tenant-aware filtering.
      publish() delivers only to subscribers whose tenant_id matches
      event.tenant_id (or subscribers with empty tenant_id — permissive).

    Design principle:
      EventPublisher is NOT the source of truth — EventLog is.
      Subscribers that miss events should replay from EventLog on reconnect.
    """

    async def publish(self, event: ExecutionEvent) -> None:
        ...

    def subscribe(self, execution_id: str, tenant_id: str) -> asyncio.Queue[Any]:
        ...

    def unsubscribe(self, execution_id: str, queue: asyncio.Queue[Any]) -> None:
        ...

    def close(self, execution_id: str) -> None:
        ...

    def close_all(self) -> None:
        ...

    @property
    def active_executions(self) -> list[str]:
        ...

    def subscriber_count(self, execution_id: str) -> int:
        ...
