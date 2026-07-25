"""Tests for P3 Step 4 — Distributed Events layer.

Covers:
  - ExecutionEvent model with correlation context
  - EventPublisher protocol contract (structural subtyping)
  - InMemoryEventPublisher edge cases
  - create_event_publisher factory
  - Redis unavailable error
"""

import asyncio
from datetime import datetime

import pytest

from runtime.kitematic_runtime.config.settings import RuntimeSettings
from kernel.events import (
    EventPublisher,
    ExecutionEvent,
    InMemoryEventPublisher,
    create_event_publisher,
)
from kernel.events.models import EventLog, EventType
from kernel.events.redis_publisher import HAS_REDIS, RedisEventPublisher

# ── ExecutionEvent model ──────────────────────────────────────────

class TestExecutionEventModel:
    """ExecutionEvent — immutable envelope with full correlation context."""

    def test_default_fields(self):
        event = ExecutionEvent()
        assert event.event_id
        assert event.execution_id == ""
        assert event.tenant_id == ""
        assert event.agent_id is None
        assert event.event_type == ""
        assert event.payload == {}
        assert isinstance(event.created_at, datetime)
        assert event.schema_version == "1.0"

    def test_correlation_context(self):
        event = ExecutionEvent(
            execution_id="exec-123",
            tenant_id="tenant-abc",
            agent_id="agent-456",
            event_type="execution.completed",
        )
        assert event.execution_id == "exec-123"
        assert event.tenant_id == "tenant-abc"
        assert event.agent_id == "agent-456"

    def test_immutable(self):
        event = ExecutionEvent(execution_id="exec-1")
        with pytest.raises(AttributeError):
            event.execution_id = "changed"

    def test_to_dict_includes_correlation(self):
        event = ExecutionEvent(
            execution_id="exec-1",
            tenant_id="t1",
            agent_id="a1",
            event_type="execution.started",
            payload={"key": "val"},
        )
        d = event.to_dict()
        assert d["execution_id"] == "exec-1"
        assert d["tenant_id"] == "t1"
        assert d["agent_id"] == "a1"
        assert d["event_type"] == "execution.started"
        assert d["payload"]["key"] == "val"
        assert "created_at" in d
        assert d["schema_version"] == "1.0"

    def test_event_type_enum_serialization(self):
        event = ExecutionEvent(event_type=EventType.LOOP_STARTED)
        d = event.to_dict()
        assert d["event_type"] == "LOOP_STARTED"

    def test_event_log_emit_creates_execution_events(self):
        log = EventLog("exec-1")
        ev = log.emit(EventType.LOOP_STARTED, state="init")
        assert ev.execution_id == "exec-1"
        assert ev.event_type == EventType.LOOP_STARTED
        assert ev.payload["state"] == "init"
        assert log.count == 1

    def test_event_log_append_only(self):
        log = EventLog("exec-1")
        log.emit(EventType.LOOP_STARTED)
        log.emit(EventType.POLICY_EVALUATED)
        assert log.count == 2
        events = log.events
        events.clear()
        assert log.count == 2


# ── Protocol contract tests ───────────────────────────────────────

class TestEventPublisherProtocol:
    """Verify InMemoryEventPublisher satisfies the EventPublisher protocol."""

    def test_protocol_check(self):
        assert isinstance(InMemoryEventPublisher(), EventPublisher)

    def test_protocol_methods_exist(self):
        pub = InMemoryEventPublisher()
        assert hasattr(pub, "publish")
        assert hasattr(pub, "subscribe")
        assert hasattr(pub, "unsubscribe")
        assert hasattr(pub, "close")
        assert hasattr(pub, "close_all")
        assert hasattr(pub, "active_executions")
        assert hasattr(pub, "subscriber_count")

    @pytest.mark.asyncio
    async def test_custom_publisher_satisfies_protocol(self):
        """Verify structural subtyping works with a minimal custom publisher."""
        import asyncio

        class CustomPublisher:
            def __init__(self):
                self._queues: dict[str, list] = {}

            async def publish(self, event):
                for q in self._queues.get(event.execution_id, []):
                    q.put_nowait(event.to_dict())

            def subscribe(self, execution_id):
                q = asyncio.Queue()
                self._queues.setdefault(execution_id, []).append(q)
                return q

            def unsubscribe(self, execution_id, queue):
                subs = self._queues.get(execution_id, [])
                if queue in subs:
                    subs.remove(queue)

            def close(self, execution_id):
                for q in self._queues.get(execution_id, []):
                    q.put_nowait(None)
                self._queues.pop(execution_id, None)

            def close_all(self):
                for eid in list(self._queues.keys()):
                    self.close(eid)

            @property
            def active_executions(self):
                return list(self._queues.keys())

            def subscriber_count(self, execution_id):
                return len(self._queues.get(execution_id, []))

        assert isinstance(CustomPublisher(), EventPublisher)

    def test_runtime_checkable(self):
        import typing
        assert typing.is_typeddict(EventPublisher) is False
        assert hasattr(EventPublisher, "__instancecheck__")


# ── InMemoryEventPublisher tests ──────────────────────────────────

class TestInMemoryEventPublisher:
    """InMemoryEventPublisher — additional edge cases beyond existing tests."""

    @pytest.mark.asyncio
    async def test_publish_with_executionevent(self):
        pub = InMemoryEventPublisher()
        queue = pub.subscribe("exec-1")
        event = ExecutionEvent(
            execution_id="exec-1",
            event_type="test.event",
            payload={"msg": "hello"},
        )
        await pub.publish(event)
        received = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert received["event_type"] == "test.event"
        assert received["payload"]["msg"] == "hello"
        assert received["execution_id"] == "exec-1"

    @pytest.mark.asyncio
    async def test_publish_backward_compat_dict(self):
        pub = InMemoryEventPublisher()
        queue = pub.subscribe("exec-1")
        await pub.publish("exec-1", {"type": "old.style", "msg": "compat"})
        received = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert received["type"] == "old.style"
        assert received["msg"] == "compat"

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent_queue(self):
        pub = InMemoryEventPublisher()
        queue = asyncio.Queue()
        pub.unsubscribe("exec-none", queue)
        assert pub.subscriber_count("exec-none") == 0

    @pytest.mark.asyncio
    async def test_close_idempotent(self):
        pub = InMemoryEventPublisher()
        pub.close("exec-does-not-exist")
        assert "exec-does-not-exist" not in pub.active_executions

    @pytest.mark.asyncio
    async def test_close_all_with_no_subscribers(self):
        pub = InMemoryEventPublisher()
        pub.close_all()
        assert pub.active_executions == []

    @pytest.mark.asyncio
    async def test_multiple_executions_with_mixed_publish(self):
        pub = InMemoryEventPublisher()
        q1 = pub.subscribe("exec-1")
        q2 = pub.subscribe("exec-2")

        await pub.publish(ExecutionEvent(
            execution_id="exec-1",
            event_type="event.a",
        ))
        await pub.publish("exec-2", {"type": "event.b"})

        r1 = await asyncio.wait_for(q1.get(), timeout=1.0)
        assert r1["event_type"] == "event.a"

        r2 = await asyncio.wait_for(q2.get(), timeout=1.0)
        assert r2["type"] == "event.b"

    @pytest.mark.asyncio
    async def test_close_removes_from_active(self):
        pub = InMemoryEventPublisher()
        pub.subscribe("exec-1")
        pub.subscribe("exec-2")
        pub.close("exec-1")
        assert "exec-1" not in pub.active_executions
        assert "exec-2" in pub.active_executions

    @pytest.mark.asyncio
    async def test_subscribe_multiple_times_same_id(self):
        pub = InMemoryEventPublisher()
        q1 = pub.subscribe("exec-1")
        q2 = pub.subscribe("exec-1")
        assert pub.subscriber_count("exec-1") == 2
        assert q1 is not q2


# ── Factory tests ─────────────────────────────────────────────────

class TestCreateEventPublisher:
    """create_event_publisher factory tests."""

    def test_default_memory(self):
        settings = RuntimeSettings()
        pub = create_event_publisher(settings)
        assert isinstance(pub, InMemoryEventPublisher)

    def test_explicit_memory(self):
        settings = RuntimeSettings(event_backend="memory")
        pub = create_event_publisher(settings)
        assert isinstance(pub, InMemoryEventPublisher)

    @pytest.mark.asyncio
    async def test_memory_publisher_works(self):
        settings = RuntimeSettings(event_backend="memory")
        pub = create_event_publisher(settings)
        queue = pub.subscribe("exec-1")
        event = ExecutionEvent(execution_id="exec-1")
        await pub.publish(event)
        received = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert received["execution_id"] == "exec-1"

    def test_unknown_backend_raises(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="Invalid event_backend"):
            RuntimeSettings(event_backend="nats")

    def test_redis_without_url_raises(self):
        settings = RuntimeSettings(event_backend="redis", redis_url="")
        with pytest.raises(ValueError, match="redis_url is required"):
            create_event_publisher(settings)

    def test_redis_backend_returned_when_url_set(self):
        if not HAS_REDIS:
            pytest.skip("redis package not installed")
        settings = RuntimeSettings(
            event_backend="redis",
            redis_url="redis://localhost:6379",
        )
        pub = create_event_publisher(settings)
        assert isinstance(pub, RedisEventPublisher)


# ── Redis unavailable tests ───────────────────────────────────────

class TestRedisUnavailable:
    """RedisEventPublisher when redis package is not installed."""

    def test_redis_not_imported_raises_at_init(self):
        if HAS_REDIS:
            pytest.skip("redis package is installed — cannot test unavailable path")
        with pytest.raises(RuntimeError, match="requires the 'redis' package"):
            RedisEventPublisher(redis_url="redis://localhost:6379")

    @pytest.mark.asyncio
    async def test_redis_publisher_requires_package(self):
        if HAS_REDIS:
            pytest.skip("redis package is installed — cannot test unavailable path")
        with pytest.raises(RuntimeError, match="requires the 'redis' package"):
            RedisEventPublisher(redis_url="redis://localhost:6379")


# ── Config integration ────────────────────────────────────────────

class TestEventSettings:
    """RuntimeSettings event_backend configuration."""

    def test_default(self):
        s = RuntimeSettings()
        assert s.event_backend == "memory"
        assert s.redis_url == ""
        assert s.event_channel_prefix == "kitematic"

    def test_invalid_backend_raises(self):
        with pytest.raises(ValueError, match="Invalid event_backend"):
            RuntimeSettings(event_backend="kafka")

    def test_redis_config(self):
        s = RuntimeSettings(
            event_backend="redis",
            redis_url="redis://localhost:6379/0",
            event_channel_prefix="myapp",
        )
        assert s.event_backend == "redis"
        assert s.redis_url == "redis://localhost:6379/0"
        assert s.event_channel_prefix == "myapp"

    def test_env_vars(self, monkeypatch):
        monkeypatch.setenv("KITEMATIC_EVENT_BACKEND", "redis")
        monkeypatch.setenv("KITEMATIC_REDIS_URL", "redis://env:6379")
        monkeypatch.setenv("KITEMATIC_EVENT_CHANNEL_PREFIX", "env-prefix")
        s = RuntimeSettings()
        assert s.event_backend == "redis"
        assert s.redis_url == "redis://env:6379"
        assert s.event_channel_prefix == "env-prefix"
