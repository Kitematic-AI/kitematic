"""Tests for the EventPublisher — in-memory event broker."""

import asyncio

import pytest

from api.events.publisher import EventPublisher


class TestEventPublisher:
    """EventPublisher tests."""

    @pytest.mark.asyncio
    async def test_subscribe_returns_queue(self):
        pub = EventPublisher()
        queue = pub.subscribe("exec-1")
        assert isinstance(queue, asyncio.Queue)
        assert pub.subscriber_count("exec-1") == 1

    @pytest.mark.asyncio
    async def test_publish_delivers_to_subscribers(self):
        pub = EventPublisher()
        queue = pub.subscribe("exec-1")
        event = {"type": "phase.started", "phase": "POLICY_EVALUATION"}

        await pub.publish("exec-1", event)
        received = await asyncio.wait_for(queue.get(), timeout=1.0)

        assert received == event

    @pytest.mark.asyncio
    async def test_publish_multiple_events(self):
        pub = EventPublisher()
        queue = pub.subscribe("exec-1")

        await pub.publish("exec-1", {"seq": 1})
        await pub.publish("exec-1", {"seq": 2})
        await pub.publish("exec-1", {"seq": 3})

        for i in range(1, 4):
            received = await asyncio.wait_for(queue.get(), timeout=1.0)
            assert received["seq"] == i

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_subscriber(self):
        pub = EventPublisher()
        queue = pub.subscribe("exec-1")
        assert pub.subscriber_count("exec-1") == 1

        pub.unsubscribe("exec-1", queue)
        assert pub.subscriber_count("exec-1") == 0

        # Unsubscribed subscriber should no longer receive events
        await pub.publish("exec-1", {"msg": "hello"})
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.get(), timeout=0.1)

    @pytest.mark.asyncio
    async def test_close_sends_sentinel_and_clears(self):
        pub = EventPublisher()
        queue = pub.subscribe("exec-1")

        pub.close("exec-1")

        received = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert received is None
        assert pub.subscriber_count("exec-1") == 0
        assert "exec-1" not in pub.active_executions

    @pytest.mark.asyncio
    async def test_multiple_subscribers_same_execution(self):
        pub = EventPublisher()
        q1 = pub.subscribe("exec-1")
        q2 = pub.subscribe("exec-1")

        await pub.publish("exec-1", {"msg": "broadcast"})

        r1 = await asyncio.wait_for(q1.get(), timeout=1.0)
        r2 = await asyncio.wait_for(q2.get(), timeout=1.0)
        assert r1 == {"msg": "broadcast"}
        assert r2 == {"msg": "broadcast"}

    @pytest.mark.asyncio
    async def test_multiple_executions_isolated(self):
        pub = EventPublisher()
        q1 = pub.subscribe("exec-1")
        q2 = pub.subscribe("exec-2")

        await pub.publish("exec-1", {"msg": "only exec-1"})

        r1 = await asyncio.wait_for(q1.get(), timeout=1.0)
        assert r1["msg"] == "only exec-1"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(q2.get(), timeout=0.1)

    @pytest.mark.asyncio
    async def test_publish_to_no_subscribers(self):
        pub = EventPublisher()
        await pub.publish("exec-none", {"msg": "nobody listens"})

    @pytest.mark.asyncio
    async def test_active_executions_property(self):
        pub = EventPublisher()
        assert pub.active_executions == []

        pub.subscribe("exec-1")
        pub.subscribe("exec-2")
        assert set(pub.active_executions) == {"exec-1", "exec-2"}

        pub.close("exec-1")
        assert "exec-1" not in pub.active_executions

    @pytest.mark.asyncio
    async def test_subscriber_count(self):
        pub = EventPublisher()
        pub.subscribe("exec-1")
        pub.subscribe("exec-1")
        pub.subscribe("exec-2")

        assert pub.subscriber_count("exec-1") == 2
        assert pub.subscriber_count("exec-2") == 1
        assert pub.subscriber_count("exec-3") == 0

    @pytest.mark.asyncio
    async def test_events_ordered(self):
        pub = EventPublisher()
        queue = pub.subscribe("exec-1")

        await pub.publish("exec-1", {"seq": 1, "ts": "2024-01-01T00:00:00"})
        await pub.publish("exec-1", {"seq": 2, "ts": "2024-01-01T00:00:01"})

        r1 = await asyncio.wait_for(queue.get(), timeout=1.0)
        r2 = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert r1["seq"] == 1
        assert r2["seq"] == 2
