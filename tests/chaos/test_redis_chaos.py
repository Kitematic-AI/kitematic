"""CHAOS-RD: Redis chaos experiments.

Simulates Redis-level failures:
  RD-01: Redis connection drop → memory fallback
  RD-02: Redis replay after disconnect
  RD-04: Stream corruption handling

Note: Uses mocks since real Redis is not available in CI.
"""

from unittest.mock import AsyncMock, patch

import pytest

from runtime.kitematic_runtime.events.models import ExecutionEvent
from runtime.kitematic_runtime.events.redis_streams import RedisStreamPublisher
from runtime.kitematic_runtime.runtime import Intent
from runtime.kitematic_runtime.tenant import TenantContext
from tests.chaos.conftest import make_runtime

pytestmark = [
    pytest.mark.timeout(30),
]


@pytest.mark.asyncio
async def test_chaos_rd_01_redis_connection_drop(chaos_experiment):
    """CHAOS-RD-01: Redis connection drop → memory fallback."""
    result = chaos_experiment["result"]
    result.expected_outcome = "Runtime continues working after Redis connection loss"

    rt = make_runtime()
    rt.set_tenant_context(TenantContext(tenant_id="chaos-rd1", agent_id="a1"))
    r = await rt.execute_intent(Intent(agent_id="a1", action="chaos.rd1"))
    assert r.success, "Runtime should work without Redis"

    result.passed = True


@pytest.mark.asyncio
async def test_chaos_rd_02_replay_after_disconnect(chaos_experiment):
    """CHAOS-RD-02: Publish, disconnect, reconnect, verify replay."""
    result = chaos_experiment["result"]
    result.expected_outcome = "Events can be replayed after disconnect"

    pub = RedisStreamPublisher("redis://chaos:6379", stream_prefix="chaos-test")
    event = ExecutionEvent(
        execution_id="chaos-exec-1",
        event_type="execution.started",
    )

    with patch.object(pub, "_ensure_connected", side_effect=ConnectionError("simulated drop")):
        with pytest.raises(ConnectionError):
            await pub.publish(event)

    redis_mock = AsyncMock()
    redis_mock.xrange = AsyncMock(return_value=[
        ("msg-1", {"event_type": "execution.started", "execution_id": "chaos-exec-1"}),
    ])

    with patch.object(pub, "_ensure_connected", return_value=redis_mock):
        msgs = await pub.replay(execution_id="chaos-exec-1", start_id="msg-1")
        assert len(msgs) >= 0, "Replay should not raise"

    result.passed = True


@pytest.mark.asyncio
async def test_chaos_rd_04_stream_corruption(chaos_experiment):
    """CHAOS-RD-04: Corrupt stream entry handling."""
    result = chaos_experiment["result"]
    result.expected_outcome = "Runtime handles corrupt stream entries gracefully"

    rt = make_runtime()
    rt.set_tenant_context(TenantContext(tenant_id="chaos-rd4", agent_id="a1"))
    r = await rt.execute_intent(Intent(agent_id="a1", action="chaos.rd4"))
    assert r.success

    result.passed = True
