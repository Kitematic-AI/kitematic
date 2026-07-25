"""Tests for P4.2 — Redis Streams event publisher.

Covers:
  - Protocol conformance
  - Construction and configuration
  - Factory routing
  - Local queue delivery (same-process subscribers)
  - Consumer group management (with mocks)
  - Stream publish/ack/replay (with mocks)
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from runtime.kitematic_runtime.config.settings import RuntimeSettings
from kernel.events.factory import create_event_publisher
from kernel.events.models import ExecutionEvent
from kernel.events.protocol import EventPublisher

# ── Helper ──────────────────────────────────────────────────────────

def make_event(execution_id: str = "exec-1", tenant_id: str = "", **kw):
    return ExecutionEvent(
        execution_id=execution_id,
        tenant_id=tenant_id,
        agent_id=kw.get("agent_id", "a1"),
        event_type=kw.get("event_type", "test.event"),
        payload=kw.get("payload", {"msg": "hello"}),
    )


@pytest.fixture
def mock_redis():
    with patch("kernel.events.redis_streams.aioredis") as mocked:
        mocked.from_url.return_value = AsyncMock()
        yield mocked


# ── Construction & Protocol ───────────────────────────────────────

class TestRedisStreamPublisherConstruction:
    """Construction and protocol contract."""

    def test_requires_redis_package(self):
        with patch("kernel.events.redis_streams.HAS_REDIS", False):
            from kernel.events.redis_streams import RedisStreamPublisher
            with pytest.raises(RuntimeError, match="requires the 'redis' package"):
                RedisStreamPublisher("redis://localhost")

    def test_default_instance_id(self):
        from kernel.events.redis_streams import RedisStreamPublisher
        pub = RedisStreamPublisher("redis://localhost:6379")
        assert pub._prefix == "kitematic"
        assert pub._instance_id.startswith("inst-")

    def test_custom_instance_id(self):
        from kernel.events.redis_streams import RedisStreamPublisher
        pub = RedisStreamPublisher("redis://localhost:6379", instance_id="worker-1")
        assert pub._instance_id == "worker-1"

    def test_meets_event_publisher_protocol(self):
        from kernel.events.redis_streams import RedisStreamPublisher
        pub = RedisStreamPublisher("redis://localhost")
        assert isinstance(pub, EventPublisher)

    def test_stream_key_format(self):
        from kernel.events.redis_streams import RedisStreamPublisher
        pub = RedisStreamPublisher("redis://localhost", stream_prefix="myapp")
        assert pub._stream_key("exec-1") == "myapp:s:exec-1"

    def test_group_name_format(self):
        from kernel.events.redis_streams import RedisStreamPublisher
        pub = RedisStreamPublisher("redis://localhost", stream_prefix="myapp")
        assert pub._group_name("t1") == "myapp:g:t1"
        assert pub._group_name("") == "myapp:g:default"

    def test_consumer_name_format(self):
        from kernel.events.redis_streams import RedisStreamPublisher
        pub = RedisStreamPublisher("redis://localhost", instance_id="w1")
        assert pub._consumer_name() == "kitematic:c:w1"

    def test_different_prefixes_produce_different_keys(self):
        from kernel.events.redis_streams import RedisStreamPublisher
        pub_a = RedisStreamPublisher("redis://localhost", stream_prefix="a")
        pub_b = RedisStreamPublisher("redis://localhost", stream_prefix="b")
        assert pub_a._stream_key("exec-1") != pub_b._stream_key("exec-1")

    def test_subscribe_reuses_execution_id_list(self):
        from kernel.events.redis_streams import RedisStreamPublisher
        pub = RedisStreamPublisher("redis://localhost")
        q1 = pub.subscribe("exec-1")
        q2 = pub.subscribe("exec-1")
        assert pub.subscriber_count("exec-1") == 2
        pub.unsubscribe("exec-1", q1)
        assert pub.subscriber_count("exec-1") == 1


class TestRedisStreamPublisherLocal:
    """Tests that use local queues (no Redis connection)."""

    def test_subscribe_and_unsubscribe(self):
        from kernel.events.redis_streams import RedisStreamPublisher
        pub = RedisStreamPublisher("redis://localhost")
        q = pub.subscribe("exec-1", tenant_id="t1")
        assert pub.subscriber_count("exec-1") == 1
        pub.unsubscribe("exec-1", q)
        assert pub.subscriber_count("exec-1") == 0

    def test_active_executions(self):
        from kernel.events.redis_streams import RedisStreamPublisher
        pub = RedisStreamPublisher("redis://localhost")
        pub.subscribe("exec-1")
        pub.subscribe("exec-2")
        assert sorted(pub.active_executions) == ["exec-1", "exec-2"]

    def test_close_removes_execution(self):
        from kernel.events.redis_streams import RedisStreamPublisher
        pub = RedisStreamPublisher("redis://localhost")
        pub.subscribe("exec-1")
        pub.close("exec-1")
        assert pub.active_executions == []

    def test_close_all(self):
        from kernel.events.redis_streams import RedisStreamPublisher
        pub = RedisStreamPublisher("redis://localhost")
        pub.subscribe("exec-1")
        pub.subscribe("exec-2")
        pub.close_all()
        assert pub.active_executions == []

    def test_subscriber_count_no_subs(self):
        from kernel.events.redis_streams import RedisStreamPublisher
        pub = RedisStreamPublisher("redis://localhost")
        assert pub.subscriber_count("exec-none") == 0


@pytest.mark.usefixtures("mock_redis")
class TestRedisStreamPublisherWithMock:
    """Tests with mocked Redis client (no real connection needed)."""

    @pytest.mark.asyncio
    async def test_publish_calls_xadd(self, mock_redis):
        from kernel.events.redis_streams import RedisStreamPublisher
        pub = RedisStreamPublisher("redis://localhost:6379")
        event = make_event(execution_id="exec-1")
        await pub.publish(event)
        redis = await pub._ensure_connected()
        redis.xadd.assert_awaited_once()
        args, _ = redis.xadd.call_args
        stream_key = args[0]
        assert stream_key == "kitematic:s:exec-1"

    @pytest.mark.asyncio
    async def test_publish_delivers_to_local_queues(self, mock_redis):
        from kernel.events.redis_streams import RedisStreamPublisher
        pub = RedisStreamPublisher("redis://localhost")
        q = pub.subscribe("exec-1", tenant_id="t1")
        event = make_event(execution_id="exec-1", tenant_id="t1")
        await pub.publish(event)
        result = await asyncio.wait_for(q.get(), timeout=1)
        assert result["__event_type__"] == "test.event"
        assert result["__tenant_id__"] == "t1"

    @pytest.mark.asyncio
    async def test_publish_tenant_isolation(self, mock_redis):
        from kernel.events.redis_streams import RedisStreamPublisher
        pub = RedisStreamPublisher("redis://localhost")
        q_tenant_a = pub.subscribe("exec-1", tenant_id="tenant-a")
        pub.subscribe("exec-1", tenant_id="tenant-b")
        event = make_event(execution_id="exec-1", tenant_id="tenant-b")
        await pub.publish(event)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(q_tenant_a.get(), timeout=0.1)

    @pytest.mark.asyncio
    async def test_ensure_consumer_group_creates_group(self, mock_redis):
        from kernel.events.redis_streams import RedisStreamPublisher
        pub = RedisStreamPublisher("redis://localhost", instance_id="w1")
        pub._stream_keys.add("kitematic:s:exec-1")
        redis = await pub._ensure_connected()
        group = await pub.ensure_consumer_group(tenant_id="t1")
        assert group == "kitematic:g:t1"
        redis.xgroup_create.assert_awaited()

    @pytest.mark.asyncio
    async def test_read_messages(self, mock_redis):
        from kernel.events.redis_streams import RedisStreamPublisher
        pub = RedisStreamPublisher("redis://localhost")
        pub._stream_keys.add("kitematic:s:exec-1")
        redis = await pub._ensure_connected()
        redis.xreadgroup.return_value = [
            ("kitematic:s:exec-1", [("msg-1", {"event_type": "test.event", "__tenant_id__": "t1"})]),
        ]
        msgs = await pub.read_messages(tenant_id="t1")
        assert len(msgs) == 1
        assert msgs[0]["id"] == "msg-1"

    @pytest.mark.asyncio
    async def test_acknowledge(self, mock_redis):
        from kernel.events.redis_streams import RedisStreamPublisher
        pub = RedisStreamPublisher("redis://localhost")
        redis = await pub._ensure_connected()
        await pub.acknowledge("stream:s:exec-1", "msg-1", tenant_id="t1")
        redis.xack.assert_awaited_with("stream:s:exec-1", "kitematic:g:t1", "msg-1")

    @pytest.mark.asyncio
    async def test_replay(self, mock_redis):
        from kernel.events.redis_streams import RedisStreamPublisher
        pub = RedisStreamPublisher("redis://localhost")
        redis = await pub._ensure_connected()
        redis.xrange.return_value = [
            ("msg-1", {"event_type": "execution.started"}),
        ]
        msgs = await pub.replay(execution_id="exec-1")
        assert len(msgs) == 1
        assert msgs[0]["id"] == "msg-1"

    @pytest.mark.asyncio
    async def test_trim(self, mock_redis):
        from kernel.events.redis_streams import RedisStreamPublisher
        pub = RedisStreamPublisher("redis://localhost")
        redis = await pub._ensure_connected()
        await pub.trim(execution_id="exec-1", maxlen=5000)
        redis.xtrim.assert_awaited()

    @pytest.mark.asyncio
    async def test_close_removes_stream_key(self, mock_redis):
        from kernel.events.redis_streams import RedisStreamPublisher
        pub = RedisStreamPublisher("redis://localhost")
        pub._stream_keys.add("kitematic:s:exec-1")
        pub.close("exec-1")
        assert "kitematic:s:exec-1" not in pub._stream_keys

    def test_close_all_clears_local_queues(self):
        from kernel.events.redis_streams import RedisStreamPublisher
        pub = RedisStreamPublisher("redis://localhost")
        pub.subscribe("exec-1")
        pub.subscribe("exec-2")
        pub.close_all()
        assert pub.active_executions == []


# ── Factory routing ────────────────────────────────────────────────

class TestFactoryForRedisStreams:
    """Factory correctly routes to RedisStreamPublisher."""

    def test_factory_returns_stream_publisher(self):
        settings = RuntimeSettings(
            event_backend="redis_streams",
            redis_url="redis://localhost:6379",
            event_channel_prefix="kt",
        )
        pub = create_event_publisher(settings)
        from kernel.events.redis_streams import RedisStreamPublisher
        assert isinstance(pub, RedisStreamPublisher)

    def test_legacy_redis_pubsub_still_works(self):
        settings = RuntimeSettings(
            event_backend="redis",
            redis_url="redis://localhost:6379",
        )
        pub = create_event_publisher(settings)
        from kernel.events.redis_publisher import RedisEventPublisher
        assert isinstance(pub, RedisEventPublisher)

    def test_memory_fallback(self):
        settings = RuntimeSettings(event_backend="memory")
        pub = create_event_publisher(settings)
        from kernel.events.memory import InMemoryEventPublisher
        assert isinstance(pub, InMemoryEventPublisher)

    def test_streams_backend_alias(self):
        settings = RuntimeSettings(
            event_backend="streams",
            redis_url="redis://localhost:6379",
        )
        pub = create_event_publisher(settings)
        from kernel.events.redis_streams import RedisStreamPublisher
        assert isinstance(pub, RedisStreamPublisher)

    def test_pubsub_backend_alias(self):
        settings = RuntimeSettings(
            event_backend="redis_pubsub",
            redis_url="redis://localhost:6379",
        )
        pub = create_event_publisher(settings)
        from kernel.events.redis_publisher import RedisEventPublisher
        assert isinstance(pub, RedisEventPublisher)

    def test_unknown_backend_raises(self):
        with pytest.raises(Exception, match="Invalid event_backend"):
            RuntimeSettings(event_backend="kafka")

    def test_streams_requires_redis_url(self):
        settings = RuntimeSettings(event_backend="redis_streams", redis_url="")
        with pytest.raises(ValueError, match="redis_url is required"):
            create_event_publisher(settings)
