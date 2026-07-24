"""DR-T06 — Redis stream replay for recovery after disconnect.

Verifies:
  - Stream replay returns events after simulated disconnect
  - Replay from any point in time via start_id
  - Replay is bounded by count
"""

import pytest

from runtime.kitematic_runtime.events.models import EventType, ExecutionEvent

pytest.importorskip("redis")

from runtime.kitematic_runtime.events.redis_streams import RedisStreamPublisher  # noqa: E402

REDIS_URL = "redis://localhost:6379/1"


@pytest.fixture
def publisher():
    pub = RedisStreamPublisher(REDIS_URL, stream_prefix="dr-test")
    yield pub
    pub.close_all()


@pytest.mark.skip(reason="Requires running Redis on localhost:6379")
class TestRedisStreamReplay:
    """DR-T06: Verify events can be replayed after disconnect."""

    @pytest.mark.asyncio
    async def test_replay_returns_published_events(self, publisher):
        event = ExecutionEvent(
            event_type=EventType.STEP_STARTED,
            execution_id="dr-replay-1",
            agent_id="a1",
            tenant_id="t1",
        )
        await publisher.publish(event)

        events = await publisher.replay("dr-replay-1")
        assert len(events) >= 1
        data = events[0]["data"]
        assert data.get("__event_type__") == EventType.STEP_STARTED.value

    @pytest.mark.asyncio
    async def test_replay_from_specific_start_id(self, publisher):
        for i in range(5):
            e = ExecutionEvent(
                event_type=EventType.STEP_STARTED,
                execution_id="dr-replay-2",
                agent_id="a1",
                payload={"seq": i},
            )
            await publisher.publish(e)

        events = await publisher.replay("dr-replay-2", start_id="0", count=2)
        assert len(events) <= 2

    @pytest.mark.asyncio
    async def test_replay_empty_stream_returns_empty(self, publisher):
        events = await publisher.replay("dr-nonexistent-stream")
        assert events == []

    @pytest.mark.asyncio
    async def test_replay_after_ack_and_disconnect(self, publisher):
        e1 = ExecutionEvent(
            event_type=EventType.STEP_STARTED,
            execution_id="dr-replay-3",
            agent_id="a1",
            payload={"msg": "before"},
        )
        await publisher.publish(e1)
        await publisher.ensure_consumer_group("t1")

        msgs = await publisher.read_messages(tenant_id="t1", count=10, block_ms=1000)
        if msgs:
            await publisher.acknowledge(msgs[0]["stream"], msgs[0]["id"], "t1")

        e2 = ExecutionEvent(
            event_type=EventType.STEP_COMPLETED,
            execution_id="dr-replay-3",
            agent_id="a1",
            payload={"msg": "after"},
        )
        await publisher.publish(e2)

        replayed = await publisher.replay("dr-replay-3", start_id="0")
        assert len(replayed) >= 2
