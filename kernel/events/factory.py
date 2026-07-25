from __future__ import annotations

from runtime.kitematic_runtime.config.settings import RuntimeSettings
from kernel.events.memory import InMemoryEventPublisher
from kernel.events.protocol import EventPublisher


def create_event_publisher(settings: RuntimeSettings) -> EventPublisher:
    """Create an EventPublisher based on runtime settings.

    Args:
        settings: RuntimeSettings with event_backend configuration.

    Returns:
        An EventPublisher implementation (InMemory, Redis Pub/Sub, or Redis Streams).

    Raises:
        ValueError: If event_backend is "redis" or "redis_streams" but no redis_url is set.
        RuntimeError: If redis package is not installed.
    """
    backend = settings.event_backend.lower()

    if backend == "memory":
        return InMemoryEventPublisher()

    if backend in ("redis", "redis_pubsub"):
        if not settings.redis_url:
            raise ValueError(
                "redis_url is required when event_backend is 'redis'"
            )
        from kernel.events.redis_publisher import RedisEventPublisher
        return RedisEventPublisher(
            redis_url=settings.redis_url,
            channel_prefix=settings.event_channel_prefix,
        )

    if backend in ("redis_streams", "streams"):
        if not settings.redis_url:
            raise ValueError(
                "redis_url is required when event_backend is 'redis_streams'"
            )
        from kernel.events.redis_streams import RedisStreamPublisher
        return RedisStreamPublisher(
            redis_url=settings.redis_url,
            stream_prefix=settings.event_channel_prefix,
        )

    raise ValueError(
        f"Unknown event_backend: {backend!r}. "
        f"Must be one of: 'memory', 'redis', 'redis_streams'"
    )
