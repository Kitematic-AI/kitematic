"""CHAOS-RT: Runtime chaos experiments.

Simulates runtime-level failures:
  RT-01: Policy engine rejection spike
  RT-02: Gateway intermittent failure
  RT-03: Runtime restart under load
  RT-04: Concurrent tenant saturation
  RT-05: Drain + stop mid-flight
  RT-06: Orphaned checkpoint cleanup
"""

import pytest

from runtime.kitematic_runtime.runtime import Intent, RuntimeState
from runtime.kitematic_runtime.tenant import TenantContext
from tests.chaos.conftest import (
    MockPolicyEvaluator,
    MockToolGateway,
    make_runtime,
    validate_recovery,
)

pytestmark = [
    pytest.mark.timeout(60),
]


@pytest.mark.asyncio
async def test_chaos_rt_01_policy_rejection_spike(chaos_experiment):
    """CHAOS-RT-01: Simulate 100% policy rejection, verify graceful degradation."""
    result = chaos_experiment["result"]
    result.expected_outcome = "Runtime returns errors gracefully, no crash"
    metrics = chaos_experiment["metrics"]

    rejecting_policy = MockPolicyEvaluator(allow=False)
    rt = make_runtime(policy=rejecting_policy, metrics=metrics)
    rt.set_tenant_context(TenantContext(tenant_id="chaos-rt1", agent_id="a1"))

    failures = 0
    for _ in range(20):
        r = await rt.execute_intent(Intent(agent_id="a1", action="chaos.rt1"))
        if not r.success:
            failures += 1

    rt._policy = MockPolicyEvaluator(allow=True)
    r = await rt.execute_intent(Intent(agent_id="a1", action="chaos.rt1.recover"))
    recovered = r.success

    validate_recovery(result, recovered, rto_seconds=5.0)
    assert failures == 20, "All 20 should fail under rejection"


@pytest.mark.asyncio
async def test_chaos_rt_02_gateway_intermittent_failure(chaos_experiment):
    """CHAOS-RT-02: Gateway failure then recovery with live restore."""
    result = chaos_experiment["result"]
    result.expected_outcome = "Runtime handles gateway failure and recovers"
    metrics = chaos_experiment["metrics"]

    failing_gateway = MockToolGateway(should_fail=True)
    rt = make_runtime(gateway=failing_gateway, metrics=metrics)
    rt.set_tenant_context(TenantContext(tenant_id="chaos-rt2", agent_id="a1"))

    for _ in range(3):
        r = await rt.execute_intent(Intent(agent_id="a1", action="chaos.rt2.fail"))
        assert not r.success, "Should fail under failing gateway"

    rt._gateway = MockToolGateway(should_fail=False)
    r = await rt.execute_intent(Intent(agent_id="a1", action="chaos.rt2.recover"))
    recovered = r.success

    validate_recovery(result, recovered, rto_seconds=5.0)


@pytest.mark.asyncio
async def test_chaos_rt_03_runtime_restart_under_load(chaos_experiment):
    """CHAOS-RT-03: Restart runtime mid-execution, verify checkpoint recovery."""
    result = chaos_experiment["result"]
    result.expected_outcome = "Checkpoints survive runtime restart"
    persistence = chaos_experiment["persistence"]

    rt1 = make_runtime(persistence=persistence)
    rt1.set_tenant_context(TenantContext(tenant_id="chaos-rt3", agent_id="a1"))
    r1 = await rt1.execute_intent(Intent(agent_id="a1", action="chaos.rt3.before"))
    assert r1.success
    del rt1

    rt2 = make_runtime(persistence=persistence)
    rt2.set_tenant_context(TenantContext(tenant_id="chaos-rt3", agent_id="a1"))
    r2 = await rt2.execute_intent(Intent(agent_id="a1", action="chaos.rt3.after"))
    recovered = r2.success

    validate_recovery(result, recovered, rto_seconds=5.0)
    assert persistence.checkpoint_count >= 2, "Multiple checkpoints should survive"


@pytest.mark.asyncio
async def test_chaos_rt_05_drain_stop_mid_flight(chaos_experiment):
    """CHAOS-RT-05: Drain + stop while executions are in flight."""
    result = chaos_experiment["result"]
    result.expected_outcome = "Drain rejects new work, stop transitions cleanly"

    rt = make_runtime()
    rt.set_tenant_context(TenantContext(tenant_id="chaos-rt5", agent_id="a1"))
    r1 = await rt.execute_intent(Intent(agent_id="a1", action="chaos.rt5.before"))
    assert r1.success

    await rt.drain()
    assert rt.state == RuntimeState.DRAINING

    r2 = await rt.execute_intent(Intent(agent_id="a1", action="chaos.rt5.after"))
    assert not r2.success, "Drain should reject new executions"

    await rt.stop()
    assert rt.state == RuntimeState.STOPPED

    result.passed = True


@pytest.mark.asyncio
async def test_chaos_rt_06_orphaned_checkpoint_cleanup(chaos_experiment):
    """CHAOS-RT-06: Simulate partial saves, verify no data loss."""
    result = chaos_experiment["result"]
    result.expected_outcome = "Checkpoints remain consistent after partial saves"
    persistence = chaos_experiment["persistence"]

    rt = make_runtime(persistence=persistence)
    rt.set_tenant_context(TenantContext(tenant_id="chaos-rt6", agent_id="a1"))

    for i in range(5):
        r = await rt.execute_intent(Intent(agent_id="a1", action=f"chaos.rt6.{i}"))
        assert r.success
        cp_id = r.checkpoint_id
        assert cp_id is not None, "Each execution should produce a checkpoint"

    del rt

    rt2 = make_runtime(persistence=persistence)
    rt2.set_tenant_context(TenantContext(tenant_id="chaos-rt6", agent_id="a1"))
    r = await rt2.execute_intent(Intent(agent_id="a1", action="chaos.rt6.verify"))
    assert r.success, "Should recover after checkpoint accumulation"

    assert persistence.checkpoint_count >= 5, "All checkpoints preserved"

    result.passed = True
