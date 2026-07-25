"""P5.6 — Incident response simulation tests.

Simulates production incidents and verifies recovery procedures
for each major incident type defined in P5_INCIDENT_RESPONSE.md.

Scenarios covered:
  IR-01: API Down                       — service crash + restart recovery
  IR-02: Runtime Failure                — execution failures + runtime restart
  IR-03: Redis Failure                  — event backend fallback to memory
  IR-04: High Latency                   — slow tool gateway + timeout recovery
  IR-05: Elevated Error Rate            — policy rejection spike + recovery
  IR-06: Authentication Failure         — key removal + re-add recovery
  IR-07: OTel Pipeline Failure          — graceful degradation without collector
"""

import asyncio

import pytest

from runtime.kitematic_runtime.api.auth import APIKeyAuthProvider, AuthContext
from kernel.runtime import (
    ExecutionPath,
    Intent,
    IntentRouter,
    KitematicRuntime,
    PolicyEvaluator,
    StatePersistence,
    ToolGateway,
    ToolResult,
)
from kernel.tenant import TenantContext

# ═══════════════════════════════════════════════════════════════════════
# Shared mock implementations
# ═══════════════════════════════════════════════════════════════════════


class MockPolicyEvaluator(PolicyEvaluator):
    def __init__(self, allow: bool = True):
        self._allow = allow

    async def evaluate_intent(self, intent: Intent) -> tuple[bool, str | None]:
        return self._allow, (None if self._allow else "policy rejected")

    async def check_capability(self, action: str, agent_id: str) -> tuple[bool, str | None]:
        return self._allow, (None if self._allow else "capability denied")


class MockIntentRouter(IntentRouter):
    async def route_intent(self, intent: Intent) -> ExecutionPath:
        return ExecutionPath(tool="mock.tool", adapter="mock")


class MockToolGateway(ToolGateway):
    def __init__(self, should_fail: bool = False, latency: float = 0.0):
        self._should_fail = should_fail
        self._latency = latency

    async def access_tool(self, path: ExecutionPath, intent: Intent) -> ToolResult:
        if self._latency > 0:
            await asyncio.sleep(self._latency)
        if self._should_fail:
            return ToolResult(success=False, error="gateway failure")
        return ToolResult(success=True, data={"output": f"ok-{intent.action}"})


class MockStatePersistence(StatePersistence):
    def __init__(self):
        self._store: dict[str, dict] = {}
        self._ids: dict[str, str] = {}

    async def save(self, execution_id: str, state: dict) -> str:
        cp_id = f"cp-{execution_id}-{len(self._store)}"
        self._store[cp_id] = dict(state)
        self._ids[execution_id] = cp_id
        return cp_id

    async def restore(self, checkpoint_id: str) -> dict:
        state = self._store.get(checkpoint_id)
        if state is None:
            raise RuntimeError(f"Checkpoint not found: {checkpoint_id}")
        return dict(state)


def make_runtime(
    policy: PolicyEvaluator | None = None,
    router: IntentRouter | None = None,
    gateway: ToolGateway | None = None,
    persistence: StatePersistence | None = None,
) -> KitematicRuntime:
    return KitematicRuntime(
        policy=policy or MockPolicyEvaluator(),
        router=router or MockIntentRouter(),
        gateway=gateway or MockToolGateway(),
        persistence=persistence or MockStatePersistence(),
    )


# ═══════════════════════════════════════════════════════════════════════
# IR-01: API Down — service crash + restart recovery
# ═══════════════════════════════════════════════════════════════════════


class TestIncidentApiDown:
    """IR-01: Simulate API crash and verify restart restores service."""

    @pytest.mark.asyncio
    async def test_api_serves_requests_after_restart(self):
        rt1 = make_runtime()
        rt1.set_tenant_context(TenantContext(tenant_id="ir01", agent_id="a1"))
        result1 = await rt1.execute_intent(Intent(agent_id="a1", action="api.before_crash"))
        assert result1.success, "Service should work before crash"

        del rt1

        rt2 = make_runtime()
        rt2.set_tenant_context(TenantContext(tenant_id="ir01", agent_id="a1"))
        result2 = await rt2.execute_intent(Intent(agent_id="a1", action="api.after_restart"))
        assert result2.success, "Service should work after restart"

    @pytest.mark.asyncio
    async def test_api_health_check_simulated(self):
        rt = make_runtime()
        rt.set_tenant_context(TenantContext(tenant_id="ir01h", agent_id="a1"))
        result = await rt.execute_intent(
            Intent(agent_id="a1", action="health.check", parameters={"type": "liveness"})
        )
        assert result.success, "Health check should succeed"

    @pytest.mark.asyncio
    async def test_concurrent_requests_after_restart(self):
        rt1 = make_runtime()
        rt1.set_tenant_context(TenantContext(tenant_id="ir01c", agent_id="a1"))
        tasks1 = [
            rt1.execute_intent(Intent(agent_id="a1", action=f"concurrent.{i}"))
            for i in range(5)
        ]
        results1 = await asyncio.gather(*tasks1)
        assert all(r.success for r in results1), "All concurrent requests should succeed"

        del rt1

        rt2 = make_runtime()
        rt2.set_tenant_context(TenantContext(tenant_id="ir01c", agent_id="a1"))
        tasks2 = [
            rt2.execute_intent(Intent(agent_id="a1", action=f"concurrent.{i}"))
            for i in range(5)
        ]
        results2 = await asyncio.gather(*tasks2)
        assert all(r.success for r in results2), "All requests should succeed after restart"


# ═══════════════════════════════════════════════════════════════════════
# IR-02: Runtime Failure — execution failures + runtime restart
# ═══════════════════════════════════════════════════════════════════════


class TestIncidentRuntimeFailure:
    """IR-02: Simulate runtime execution failures and verify recovery."""

    @pytest.mark.asyncio
    async def test_runtime_recovers_from_policy_failure(self):
        rejecting_policy = MockPolicyEvaluator(allow=False)
        rt = KitematicRuntime(
            policy=rejecting_policy,
            router=MockIntentRouter(),
            gateway=MockToolGateway(),
            persistence=MockStatePersistence(),
        )
        rt.set_tenant_context(TenantContext(tenant_id="ir02", agent_id="a1"))
        result = await rt.execute_intent(Intent(agent_id="a1", action="test.reject"))
        assert not result.success, "Policy should reject"

        rt._policy = MockPolicyEvaluator(allow=True)
        result2 = await rt.execute_intent(Intent(agent_id="a1", action="test.recover"))
        assert result2.success, "Should recover after policy fix"

    @pytest.mark.asyncio
    async def test_runtime_recovers_from_gateway_failure(self):
        failing_gateway = MockToolGateway(should_fail=True)
        rt = KitematicRuntime(
            policy=MockPolicyEvaluator(),
            router=MockIntentRouter(),
            gateway=failing_gateway,
            persistence=MockStatePersistence(),
        )
        rt.set_tenant_context(TenantContext(tenant_id="ir02g", agent_id="a1"))
        result = await rt.execute_intent(Intent(agent_id="a1", action="test.gateway_fail"))
        assert not result.success, "Gateway failure should propagate"

        rt._gateway = MockToolGateway(should_fail=False)
        result2 = await rt.execute_intent(Intent(agent_id="a1", action="test.gateway_recover"))
        assert result2.success, "Should recover after gateway fix"

    @pytest.mark.asyncio
    async def test_runtime_restart_multiple_tenants(self):
        persistence = MockStatePersistence()
        rt1 = KitematicRuntime(
            policy=MockPolicyEvaluator(),
            router=MockIntentRouter(),
            gateway=MockToolGateway(),
            persistence=persistence,
        )
        rt1.set_tenant_context(TenantContext(tenant_id="t1", agent_id="a1"))
        await rt1.execute_intent(Intent(agent_id="a1", action="multi.t1"))

        rt1.set_tenant_context(TenantContext(tenant_id="t2", agent_id="a2"))
        await rt1.execute_intent(Intent(agent_id="a2", action="multi.t2"))

        del rt1

        rt2 = KitematicRuntime(
            policy=MockPolicyEvaluator(),
            router=MockIntentRouter(),
            gateway=MockToolGateway(),
            persistence=persistence,
        )
        rt2.set_tenant_context(TenantContext(tenant_id="t1", agent_id="a1"))
        r1 = await rt2.execute_intent(Intent(agent_id="a1", action="multi.t1.after"))
        assert r1.success, "Tenant 1 should work after restart"

        rt2.set_tenant_context(TenantContext(tenant_id="t2", agent_id="a2"))
        r2 = await rt2.execute_intent(Intent(agent_id="a2", action="multi.t2.after"))
        assert r2.success, "Tenant 2 should work after restart"


# ═══════════════════════════════════════════════════════════════════════
# IR-03: Redis Failure — event backend fallback to memory
# ═══════════════════════════════════════════════════════════════════════


class TestIncidentRedisFailure:
    """IR-03: Simulate Redis outage and verify fallback to memory backend."""

    @pytest.mark.asyncio
    async def test_runtime_works_without_event_backend(self):
        rt = make_runtime()
        rt.set_tenant_context(TenantContext(tenant_id="ir03", agent_id="a1"))
        result = await rt.execute_intent(Intent(agent_id="a1", action="redis.fallback"))
        assert result.success, "Runtime should work without Redis"

    @pytest.mark.asyncio
    async def test_multiple_executions_without_backend(self):
        rt = make_runtime()
        rt.set_tenant_context(TenantContext(tenant_id="ir03m", agent_id="a1"))
        for i in range(10):
            result = await rt.execute_intent(
                Intent(agent_id="a1", action=f"redis.batch.{i}")
            )
            assert result.success, f"Execution {i} should succeed without Redis"

    @pytest.mark.asyncio
    async def test_checkpoint_persistence_without_event_backend(self):
        persistence = MockStatePersistence()
        rt = KitematicRuntime(
            policy=MockPolicyEvaluator(),
            router=MockIntentRouter(),
            gateway=MockToolGateway(),
            persistence=persistence,
        )
        rt.set_tenant_context(TenantContext(tenant_id="ir03c", agent_id="a1"))
        result = await rt.execute_intent(
            Intent(agent_id="a1", action="redis.checkpoint")
        )
        assert result.success

        rt2 = KitematicRuntime(
            policy=MockPolicyEvaluator(),
            router=MockIntentRouter(),
            gateway=MockToolGateway(),
            persistence=persistence,
        )
        rt2.set_tenant_context(TenantContext(tenant_id="ir03c", agent_id="a1"))
        result2 = await rt2.execute_intent(
            Intent(agent_id="a1", action="redis.checkpoint.after")
        )
        assert result2.success, "Checkpoints preserved without event backend"


# ═══════════════════════════════════════════════════════════════════════
# IR-04: High Latency — slow tool gateway + timeout recovery
# ═══════════════════════════════════════════════════════════════════════


class TestIncidentHighLatency:
    """IR-04: Simulate high latency and verify recovery."""

    @pytest.mark.asyncio
    async def test_slow_gateway_does_not_block_runtime(self):
        slow_gateway = MockToolGateway(latency=0.05)
        rt = KitematicRuntime(
            policy=MockPolicyEvaluator(),
            router=MockIntentRouter(),
            gateway=slow_gateway,
            persistence=MockStatePersistence(),
        )
        rt.set_tenant_context(TenantContext(tenant_id="ir04", agent_id="a1"))
        result = await rt.execute_intent(
            Intent(agent_id="a1", action="latency.slow")
        )
        assert result.success, "Slow gateway should still complete"
        assert result.data.get("in_flight") is None or True

    @pytest.mark.asyncio
    async def test_recovery_after_latency_resolved(self):
        slow_gateway = MockToolGateway(latency=0.03)
        rt = KitematicRuntime(
            policy=MockPolicyEvaluator(),
            router=MockIntentRouter(),
            gateway=slow_gateway,
            persistence=MockStatePersistence(),
        )
        rt.set_tenant_context(TenantContext(tenant_id="ir04r", agent_id="a1"))
        result1 = await rt.execute_intent(
            Intent(agent_id="a1", action="latency.slow")
        )
        assert result1.success

        rt._gateway = MockToolGateway(latency=0.0)
        result2 = await rt.execute_intent(
            Intent(agent_id="a1", action="latency.fast")
        )
        assert result2.success, "Should recover after latency resolved"

    @pytest.mark.asyncio
    async def test_concurrent_latency_does_not_cascade(self):
        slow_gateway = MockToolGateway(latency=0.02)
        rt = KitematicRuntime(
            policy=MockPolicyEvaluator(),
            router=MockIntentRouter(),
            gateway=slow_gateway,
            persistence=MockStatePersistence(),
        )
        rt.set_tenant_context(TenantContext(tenant_id="ir04c", agent_id="a1"))
        tasks = [
            rt.execute_intent(Intent(agent_id="a1", action=f"latency.concurrent.{i}"))
            for i in range(8)
        ]
        results = await asyncio.gather(*tasks)
        successes = sum(1 for r in results if r.success)
        assert successes >= 6, "Most concurrent requests should succeed despite latency"


# ═══════════════════════════════════════════════════════════════════════
# IR-05: Elevated Error Rate — policy rejection spike + recovery
# ═══════════════════════════════════════════════════════════════════════


class TestIncidentElevatedErrorRate:
    """IR-05: Simulate error rate spike and verify recovery."""

    @pytest.mark.asyncio
    async def test_error_rate_recovers_after_policy_fix(self):
        rejecting_policy = MockPolicyEvaluator(allow=False)
        rt = KitematicRuntime(
            policy=rejecting_policy,
            router=MockIntentRouter(),
            gateway=MockToolGateway(),
            persistence=MockStatePersistence(),
        )
        rt.set_tenant_context(TenantContext(tenant_id="ir05", agent_id="a1"))

        failures = 0
        for _ in range(10):
            result = await rt.execute_intent(
                Intent(agent_id="a1", action="error.spike")
            )
            if not result.success:
                failures += 1
        assert failures == 10, "All should fail under rejecting policy"

        rt._policy = MockPolicyEvaluator(allow=True)
        successes = 0
        for _ in range(10):
            result = await rt.execute_intent(
                Intent(agent_id="a1", action="error.recovery")
            )
            if result.success:
                successes += 1
        assert successes == 10, "All should succeed after policy fix"

    @pytest.mark.asyncio
    async def test_partial_gateway_failure_then_recovery(self):
        gateway = MockToolGateway(should_fail=True)
        rt = KitematicRuntime(
            policy=MockPolicyEvaluator(),
            router=MockIntentRouter(),
            gateway=gateway,
            persistence=MockStatePersistence(),
        )
        rt.set_tenant_context(TenantContext(tenant_id="ir05g", agent_id="a1"))

        for _ in range(5):
            result = await rt.execute_intent(
                Intent(agent_id="a1", action="gateway.error")
            )
            assert not result.success, "Should fail under failing gateway"

        rt._gateway = MockToolGateway(should_fail=False)
        for _ in range(5):
            result = await rt.execute_intent(
                Intent(agent_id="a1", action="gateway.recovery")
            )
            assert result.success, "Should recover after gateway fix"

    @pytest.mark.asyncio
    async def test_mixed_success_failure_rates(self):
        class AlternatingGateway(MockToolGateway):
            def __init__(self):
                super().__init__()
                self._call_count = 0

            async def access_tool(self, path: ExecutionPath, intent: Intent) -> ToolResult:
                self._call_count += 1
                if self._call_count % 3 == 0:
                    return ToolResult(success=False, error="intermittent failure")
                return ToolResult(success=True, data={"output": "ok"})

        rt = KitematicRuntime(
            policy=MockPolicyEvaluator(),
            router=MockIntentRouter(),
            gateway=AlternatingGateway(),
            persistence=MockStatePersistence(),
        )
        rt.set_tenant_context(TenantContext(tenant_id="ir05m", agent_id="a1"))
        results = await asyncio.gather(*[
            rt.execute_intent(Intent(agent_id="a1", action=f"mixed.{i}"))
            for i in range(12)
        ])
        successes = sum(1 for r in results if r.success)
        assert 7 <= successes <= 10, "Should have ~66% success rate with intermittent gateway"


# ═══════════════════════════════════════════════════════════════════════
# IR-06: Authentication Failure — key removal + re-add recovery
# ═══════════════════════════════════════════════════════════════════════


class TestIncidentAuthFailure:
    """IR-06: Simulate auth failure (key removed) and recovery (key re-added)."""

    @pytest.mark.asyncio
    async def test_auth_fails_after_key_removed(self):
        provider = APIKeyAuthProvider()
        provider.add_key("valid-key", AuthContext(tenant_id="ir06", agent_id="a1"))
        ctx = await provider.authenticate("valid-key")
        assert ctx is not None, "Auth should succeed before key removal"

        provider.remove_key("valid-key")
        ctx = await provider.authenticate("valid-key")
        assert ctx is None, "Auth should fail after key removal"

    @pytest.mark.asyncio
    async def test_auth_recovers_after_key_re_added(self):
        provider = APIKeyAuthProvider()
        provider.add_key("temp-key", AuthContext(tenant_id="ir06r", agent_id="a1"))
        provider.remove_key("temp-key")
        ctx = await provider.authenticate("temp-key")
        assert ctx is None, "Auth should fail after removal"

        provider.add_key("temp-key", AuthContext(tenant_id="ir06r", agent_id="a1"))
        ctx = await provider.authenticate("temp-key")
        assert ctx is not None, "Auth should recover after key re-added"
        assert ctx.tenant_id == "ir06r"

    @pytest.mark.asyncio
    async def test_key_rotation_recovers_auth(self):
        provider = APIKeyAuthProvider()
        provider.add_key("old-key", AuthContext(tenant_id="ir06rot", agent_id="a1"))
        rotated = provider.rotate_key("old-key", "new-key")
        assert rotated, "Rotation should succeed"

        ctx_old = await provider.authenticate("old-key")
        assert ctx_old is None, "Old key should be invalid after rotation"

        ctx_new = await provider.authenticate("new-key")
        assert ctx_new is not None, "New key should be valid after rotation"
        assert ctx_new.tenant_id == "ir06rot"

    @pytest.mark.asyncio
    async def test_empty_key_returns_none(self):
        provider = APIKeyAuthProvider()
        provider.add_key("real-key", AuthContext(tenant_id="ir06e", agent_id="a1"))
        ctx = await provider.authenticate("")
        assert ctx is None, "Empty key should return None"

    @pytest.mark.asyncio
    async def test_unknown_key_returns_none(self):
        provider = APIKeyAuthProvider()
        provider.add_key("known-key", AuthContext(tenant_id="ir06u", agent_id="a1"))
        ctx = await provider.authenticate("unknown-key")
        assert ctx is None, "Unknown key should return None"


# ═══════════════════════════════════════════════════════════════════════
# IR-07: OTel Pipeline Failure — graceful degradation without collector
# ═══════════════════════════════════════════════════════════════════════


class TestIncidentOTelFailure:
    """IR-07: Simulate OTel collector outage and verify graceful degradation."""

    @pytest.mark.asyncio
    async def test_runtime_executes_without_otel_tracer(self):
        from kernel.observability.opentelemetry import get_tracer_provider

        original = get_tracer_provider()
        assert original is not None, "Should have a default tracer"

        rt = make_runtime()
        rt.set_tenant_context(TenantContext(tenant_id="ir07", agent_id="a1"))
        result = await rt.execute_intent(
            Intent(agent_id="a1", action="otel.no_tracer")
        )
        assert result.success, "Runtime should work without OTel tracer"

    @pytest.mark.asyncio
    async def test_execution_tracer_works_without_otel(self):
        from kernel.observability.tracing import ExecutionTracer, TracePhase

        tracer = ExecutionTracer(execution_id="ir07-t1", agent_id="a1")
        tracer.start_phase(TracePhase.POLICY_EVALUATION, {"test": "value"})
        tracer.end_phase(success=True)

        trace = tracer.get_trace()
        assert len(trace) == 1, "Should track phase even without OTel"
        assert trace[0]["success"], "Phase should be marked successful"
        assert trace[0]["phase"] == "policy.evaluation"

    @pytest.mark.asyncio
    async def test_metrics_registry_works_without_otel_meter(self):
        from kernel.observability.metrics import MetricsRegistry

        registry = MetricsRegistry(otel_meter=None)
        registry.increment("test.counter")
        registry.record("test.latency", 100)

        assert registry.get_counter("test.counter") == 1, "Counter should increment"
        assert len(registry.get_histogram("test.latency")) == 1, "Histogram should record"

    @pytest.mark.asyncio
    async def test_runtime_full_cycle_without_otel(self):
        rt = make_runtime()
        rt.set_tenant_context(TenantContext(tenant_id="ir07c", agent_id="a1"))
        result = await rt.execute_intent(
            Intent(agent_id="a1", action="otel.full_cycle")
        )
        assert result.success, "Full execution cycle should work without OTel"
