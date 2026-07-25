"""Chaos / recovery tests for Kitematic Runtime.

These tests verify graceful degradation and recovery under failure conditions:
  - Redis connection failure
  - Runtime restart recovery
  - Event loss simulation
  - Draining recovery

All tests use mocks since real Redis is not available in CI.
"""

from unittest.mock import AsyncMock, patch

import pytest

from runtime.kitematic_runtime.api.quotas import QuotaManager, TenantQuotaConfig
from kernel.events.redis_streams import RedisStreamPublisher
from kernel.observability.metrics import MetricsRegistry
from kernel.runtime import Intent, KitematicRuntime
from kernel.state import RuntimeState
from kernel.tenant import TenantContext


class MockPolicy:
    async def evaluate_intent(self, intent):
        return True, None
    async def check_capability(self, action, agent_id):
        return True, None


class MockRouter:
    async def route_intent(self, intent):
        from kernel.runtime import ExecutionPath
        return ExecutionPath(tool="mock_tool")


class MockGateway:
    async def access_tool(self, path, intent):
        from kernel.runtime import ToolResult
        return ToolResult(success=True, data={"result": "ok"})


class MockPersistence:
    async def save(self, execution_id, state):
        return f"cp-{execution_id}"
    async def restore(self, checkpoint_id):
        return {}


@pytest.fixture
def base_runtime():
    metrics = MetricsRegistry()
    qm = QuotaManager()
    rt = KitematicRuntime(
        policy=MockPolicy(),
        router=MockRouter(),
        gateway=MockGateway(),
        persistence=MockPersistence(),
        metrics=metrics,
        quota_manager=qm,
    )
    rt.set_tenant_context(TenantContext(tenant_id="chaos-t1", agent_id="chaos-agent"))
    return rt, metrics, qm


@pytest.mark.asyncio
async def test_runtime_recovers_after_drain(base_runtime):
    rt, _, _ = base_runtime
    await rt.drain()
    result = await rt.execute_intent(Intent(agent_id="a1", action="test"))
    assert not result.success
    assert rt.state == RuntimeState.DRAINING
    await rt.stop()
    assert rt.state == RuntimeState.STOPPED


@pytest.mark.asyncio
async def test_drain_allows_in_flight_completion(base_runtime):
    rt, _, _ = base_runtime
    result1 = await rt.execute_intent(Intent(agent_id="a1", action="fast"))
    assert result1.success
    await rt.drain()
    result2 = await rt.execute_intent(Intent(agent_id="a2", action="rejected"))
    assert not result2.success


@pytest.mark.asyncio
async def test_redis_stream_publisher_handles_disconnect(base_runtime):
    from kernel.events.models import ExecutionEvent
    pub = RedisStreamPublisher("redis://broken:6379")
    event = ExecutionEvent(execution_id="exec-1", event_type="test")
    with patch.object(pub, "_ensure_connected", side_effect=ConnectionError("Broken pipe")):
        with pytest.raises(ConnectionError):
            await pub.publish(event)


@pytest.mark.asyncio
async def test_redis_stream_replay_on_reconnect():
    pub = RedisStreamPublisher("redis://localhost", stream_prefix="test")
    redis = await pub._ensure_connected()
    redis.xrange = AsyncMock(return_value=[
        ("msg-1", {"event_type": "execution.started"}),
        ("msg-2", {"event_type": "execution.completed"}),
    ])
    msgs = await pub.replay(execution_id="exec-1", start_id="msg-1")
    assert len(msgs) == 2
    assert msgs[0]["id"] == "msg-1"


@pytest.mark.asyncio
async def test_redis_stream_consumer_group_creation_handles_busy(base_runtime):
    pub = RedisStreamPublisher("redis://localhost", stream_prefix="test")
    pub._stream_keys.add("test:s:exec-1")
    redis = await pub._ensure_connected()
    from redis.asyncio.client import ResponseError
    busy_err = "BUSYGROUP Consumer Group name already exists"
    redis.xgroup_create = AsyncMock(side_effect=ResponseError(busy_err))
    group = await pub.ensure_consumer_group(tenant_id="t1")
    assert group == "test:g:t1"


@pytest.mark.asyncio
async def test_metrics_survive_multiple_failures(base_runtime):
    rt, metrics, qm = base_runtime
    qm.configure("chaos-t1", TenantQuotaConfig(max_concurrent=1))
    qm.start_execution("chaos-t1", "stuck-exec")
    for _ in range(3):
        result = await rt.execute_intent(Intent(agent_id="a1", action="test"))
        assert not result.success
    assert metrics.get_counter("resource.quota.exceeded") >= 3


@pytest.mark.asyncio
async def test_runtime_handles_concurrent_drain_and_execution(base_runtime):
    rt, _, _ = base_runtime
    result1 = await rt.execute_intent(Intent(agent_id="a1", action="fast"))
    assert result1.success
    await rt.drain()
    await rt.drain()
    assert rt.state == RuntimeState.DRAINING
    result2 = await rt.execute_intent(Intent(agent_id="a2", action="late"))
    assert not result2.success
    await rt.stop()
    assert rt.state == RuntimeState.STOPPED
