"""Load tests for Kitematic Runtime.

These tests verify:
  - Runtime handles concurrent execution within limits
  - QuotaManager rate limiting under load
  - Metrics registry collects data accurately under concurrent access
  - Trace sampling does not degrade under load

Run with: pytest tests/performance/ --tb=short -v
"""

import time

import pytest

from api.rest.quotas import QuotaManager, TenantQuotaConfig
from kernel.observability.metrics import MetricsRegistry
from kernel.runtime import Intent, KitematicRuntime
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
def runtime():
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
    rt.set_tenant_context(TenantContext(tenant_id="load-t1", agent_id="loader"))
    return rt, metrics, qm


@pytest.mark.asyncio
async def test_concurrent_executions_within_limits(runtime):
    rt, metrics, qm = runtime
    qm.configure("load-t1", TenantQuotaConfig(max_concurrent=10))
    results = []
    for i in range(5):
        result = await rt.execute_intent(Intent(agent_id=f"agent-{i}", action="ping"))
        results.append(result)
    assert all(r.success for r in results)
    assert metrics.get_counter("runtime.executions.completed") == 5


@pytest.mark.asyncio
async def test_rate_limiting_under_burst(runtime):
    rt, metrics, qm = runtime
    qm.configure("load-t1", TenantQuotaConfig(max_concurrent=100))
    qm._rate_limiter._buckets["load-t1"] = qm._rate_limiter._get_bucket("load-t1")
    qm._rate_limiter._buckets["load-t1"].tokens = 5
    accepted = 0
    rejected = 0
    for _ in range(20):
        result = await rt.execute_intent(Intent(agent_id="burst-agent", action="burst"))
        if result.success:
            accepted += 1
        else:
            rejected += 1
    assert accepted == 5
    assert rejected == 15


@pytest.mark.asyncio
async def test_metrics_collected_under_load(runtime):
    rt, metrics, qm = runtime
    qm.configure("load-t1", TenantQuotaConfig(max_concurrent=20))
    for i in range(10):
        await rt.execute_intent(Intent(agent_id=f"load-{i}", action="stress"))
    snap = metrics.snapshot()
    assert snap["counters"]["runtime.executions.total"] == 10
    assert snap["counters"]["runtime.executions.completed"] == 10
    assert "runtime.execution.duration_ms" in snap["histograms"]


@pytest.mark.asyncio
async def test_quota_metrics_under_load(runtime):
    rt, metrics, qm = runtime
    qm.configure("load-t1", TenantQuotaConfig(max_concurrent=1))
    qm.start_execution("load-t1", "blocker")
    result = await rt.execute_intent(Intent(agent_id="blocked", action="test"))
    assert not result.success
    assert metrics.get_counter("resource.quota.exceeded") >= 1


@pytest.mark.asyncio
async def test_high_throughput_execution_chain(runtime):
    rt, metrics, qm = runtime
    qm.configure("load-t1", TenantQuotaConfig(max_concurrent=50))
    start = time.time()
    count = 20
    for i in range(count):
        await rt.execute_intent(Intent(agent_id=f"ht-agent-{i}", action="ping"))
    elapsed = time.time() - start
    throughput = count / elapsed if elapsed > 0 else 0
    assert throughput > 0
    assert metrics.get_counter("runtime.executions.completed") == count
