"""Events — runtime event models, protocols, and backends.

Provides the EventPublisher protocol and built-in InMemoryEventPublisher
for streaming execution events to WebSocket subscribers.

The runtime and API never know whether events are delivered via
in-memory queues, Redis Pub/Sub, or Redis Streams — they depend only
on the protocol.

Usage:
    from kernel.events import (
        EventPublisher,
        InMemoryEventPublisher,
        ExecutionEvent,
        create_event_publisher,
    )
"""

from kernel.events.factory import create_event_publisher
from kernel.events.memory import InMemoryEventPublisher
from kernel.events.models import EventLog, EventType, ExecutionEvent
from kernel.events.protocol import EventPublisher

try:
    from kernel.events.redis_streams import RedisStreamPublisher
    HAS_STREAMS = True
except ImportError:
    RedisStreamPublisher = None  # type: ignore[assignment,misc]
    HAS_STREAMS = False

__all__ = [
    "EventLog",
    "EventType",
    "ExecutionEvent",
    "EventPublisher",
    "InMemoryEventPublisher",
    "create_event_publisher",
]
if HAS_STREAMS:
    __all__.append("RedisStreamPublisher")
