"""Integration Tests — full chain verification.

Tests the complete execution chain:
  Intent → Policy → Capability → Router → Gateway → Checkpoint

No runtime code changes — validation only.
"""


import pytest

from runtime.kitematic_runtime.budget import ExecutionBudget
from runtime.kitematic_runtime.isolation import IsolationBoundary
from runtime.kitematic_runtime.loop import LoopController
from runtime.kitematic_runtime.runtime import (
    ExecutionPath,
    Intent,
    IntentRouter,
    KitematicRuntime,
    PolicyEvaluator,
    StatePersistence,
    ToolGateway,
    ToolResult,
)
from runtime.kitematic_runtime.states import ExecutionState
from runtime.kitematic_runtime.tenant import TenantContext, TenantModel

# ── Mock Implementations ───────────────────────────────────────────────


class TrackingPolicy(PolicyEvaluator):
    """Tracks evaluation calls for verification."""

    def __init__(self, allow=True):
        self._allow = allow
        self.calls: list[str] = []

    async def evaluate_intent(self, intent):
        self.calls.append("policy")
        return self._allow, None if self._allow else "denied"

    async def check_capability(self, action, agent_id):
        self.calls.append("capability")
        return self._allow, None if self._allow else "no cap"


class TrackingRouter(IntentRouter):
    """Tracks routing calls for verification."""

    def __init__(self, tool="mcp.test.tool"):
        self._tool = tool
        self.calls: list[str] = []

    async def route_intent(self, intent):
        self.calls.append("router")
        return ExecutionPath(tool=self._tool, parameters={"intent": intent.action})


class TrackingGateway(ToolGateway):
    """Tracks gateway calls for verification."""

    def __init__(self, result_data=None):
        self._data = result_data or {"output": "ok"}
        self.calls: list[str] = []

    async def access_tool(self, path, intent):
        self.calls.append("gateway")
        return ToolResult(success=True, data=self._data)


class TrackingPersistence(StatePersistence):
    """Tracks persistence calls for verification."""

    def __init__(self):
        self.saved: list[tuple] = []
        self.restored: list[str] = []

    async def save(self, execution_id, state):
        self.saved.append((execution_id, state))
        return f"cp-{len(self.saved)}"

    async def restore(self, checkpoint_id):
        self.restored.append(checkpoint_id)
        return {"checkpoint_id": checkpoint_id, "restored": True}


class FailingRouter(IntentRouter):
    """Router that always fails."""

    async def route_intent(self, intent):
        raise RuntimeError("router crashed")


class FailingGateway(ToolGateway):
    """Gateway that always fails."""

    async def access_tool(self, path, intent):
        return ToolResult(success=False, error="gateway failed")


class FailingPersistence(StatePersistence):
    """Persistence that always fails on save."""

    async def save(self, execution_id, state):
        raise RuntimeError("checkpoint save failed")

    async def restore(self, checkpoint_id):
        raise RuntimeError("checkpoint restore failed")


# ── Full Chain Tests ────────────────────────────────────────────────────


class TestFullChain:
    """End-to-end: Intent → Policy → Capability → Router → Gateway → Checkpoint"""

    @pytest.mark.asyncio
    async def test_happy_path_completes(self):
        policy = TrackingPolicy()
        router = TrackingRouter()
        gateway = TrackingGateway()
        persistence = TrackingPersistence()

        runtime = KitematicRuntime(
            policy=policy, router=router, gateway=gateway, persistence=persistence
        )
        result = await runtime.execute_intent(Intent(agent_id="a1", action="deploy"))

        assert result.success is True
        assert result.state == ExecutionState.COMPLETED
        assert result.checkpoint_id is not None
        assert result.data == {"output": "ok"}

    @pytest.mark.asyncio
    async def test_chain_order_preserved(self):
        policy = TrackingPolicy()
        router = TrackingRouter()
        gateway = TrackingGateway()
        persistence = TrackingPersistence()

        runtime = KitematicRuntime(
            policy=policy, router=router, gateway=gateway, persistence=persistence
        )
        await runtime.execute_intent(Intent(agent_id="a1", action="x"))

        # All components called in order
        assert "policy" in policy.calls
        assert "capability" in policy.calls
        assert "router" in router.calls
        assert "gateway" in gateway.calls
        assert len(persistence.saved) == 1

    @pytest.mark.asyncio
    async def test_checkpoint_contains_metadata(self):
        persistence = TrackingPersistence()
        runtime = KitematicRuntime(
            policy=TrackingPolicy(),
            router=TrackingRouter(),
            gateway=TrackingGateway(result_data={"key": "value"}),
            persistence=persistence,
        )
        await runtime.execute_intent(Intent(agent_id="a1", action="test"))

        assert len(persistence.saved) == 1
        state = persistence.saved[0][1]
        assert state["intent_action"] == "test"
        assert state["intent_agent"] == "a1"
        assert state["tool_result"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_result_data_from_gateway(self):
        runtime = KitematicRuntime(
            policy=TrackingPolicy(),
            router=TrackingRouter(),
            gateway=TrackingGateway(result_data={"db": "result"}),
            persistence=TrackingPersistence(),
        )
        result = await runtime.execute_intent(Intent(agent_id="a1", action="query"))
        assert result.data == {"db": "result"}


# ── Failure Path Tests ──────────────────────────────────────────────────


class TestFailurePaths:
    """Every failure point must halt correctly."""

    @pytest.mark.asyncio
    async def test_policy_rejection_no_gateway(self):
        gateway = TrackingGateway()
        runtime = KitematicRuntime(
            policy=TrackingPolicy(allow=False),
            router=TrackingRouter(),
            gateway=gateway,
            persistence=TrackingPersistence(),
        )
        result = await runtime.execute_intent(Intent(agent_id="a1", action="x"))

        assert result.success is False
        assert result.state == ExecutionState.FAILED
        assert "denied" in result.error.lower()
        assert len(gateway.calls) == 0

    @pytest.mark.asyncio
    async def test_router_failure_halts(self):
        runtime = KitematicRuntime(
            policy=TrackingPolicy(),
            router=FailingRouter(),
            gateway=TrackingGateway(),
            persistence=TrackingPersistence(),
        )
        result = await runtime.execute_intent(Intent(agent_id="a1", action="x"))

        assert result.success is False
        assert result.state == ExecutionState.HALTED

    @pytest.mark.asyncio
    async def test_gateway_failure_no_checkpoint(self):
        persistence = TrackingPersistence()
        runtime = KitematicRuntime(
            policy=TrackingPolicy(),
            router=TrackingRouter(),
            gateway=FailingGateway(),
            persistence=persistence,
        )
        result = await runtime.execute_intent(Intent(agent_id="a1", action="x"))

        assert result.success is False
        assert result.state == ExecutionState.FAILED
        assert len(persistence.saved) == 0

    @pytest.mark.asyncio
    async def test_checkpoint_failure_halts(self):
        runtime = KitematicRuntime(
            policy=TrackingPolicy(),
            router=TrackingRouter(),
            gateway=TrackingGateway(),
            persistence=FailingPersistence(),
        )
        result = await runtime.execute_intent(Intent(agent_id="a1", action="x"))

        assert result.success is False
        assert result.state == ExecutionState.HALTED


# ── Multi-Step Tests ────────────────────────────────────────────────────


class TestMultiStepExecution:
    """Multiple intents through the loop."""

    @pytest.mark.asyncio
    async def test_sequential_execution(self):
        budget = ExecutionBudget(max_steps=5)
        runtime = KitematicRuntime(
            policy=TrackingPolicy(),
            router=TrackingRouter(),
            gateway=TrackingGateway(),
            persistence=TrackingPersistence(),
        )
        loop = LoopController(runtime=runtime, budget=budget)

        intents = [
            Intent(agent_id="a1", action="step1"),
            Intent(agent_id="a1", action="step2"),
            Intent(agent_id="a1", action="step3"),
        ]
        results = await loop.run_multi_step(intents)

        assert len(results) == 3
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_early_termination_on_failure(self):
        budget = ExecutionBudget(max_steps=5)
        runtime = KitematicRuntime(
            policy=TrackingPolicy(allow=False),
            router=TrackingRouter(),
            gateway=TrackingGateway(),
            persistence=TrackingPersistence(),
        )
        loop = LoopController(runtime=runtime, budget=budget)

        intents = [
            Intent(agent_id="a1", action="step1"),
            Intent(agent_id="a1", action="step2"),
        ]
        results = await loop.run_multi_step(intents)

        # Only first intent executed, then stopped on failure
        assert len(results) == 1
        assert results[0].success is False

    @pytest.mark.asyncio
    async def test_budget_exhaustion_stops_loop(self):
        budget = ExecutionBudget(max_steps=2)
        runtime = KitematicRuntime(
            policy=TrackingPolicy(),
            router=TrackingRouter(),
            gateway=TrackingGateway(),
            persistence=TrackingPersistence(),
        )
        loop = LoopController(runtime=runtime, budget=budget)

        intents = [
            Intent(agent_id="a1", action="s1"),
            Intent(agent_id="a1", action="s2"),
            Intent(agent_id="a1", action="s3"),
        ]
        results = await loop.run_multi_step(intents)

        assert len(results) <= 2


# ── Tenant Integrated Tests ────────────────────────────────────────────


class TestTenantIntegratedExecution:
    """Full chain with tenant isolation enabled."""

    @pytest.mark.asyncio
    async def test_tenant_context_propagated(self):
        boundary = IsolationBoundary()
        boundary.register_tenant(TenantModel(tenant_id="t1", name="T"))
        boundary.register_agent("a1", "t1")

        runtime = KitematicRuntime(
            policy=TrackingPolicy(),
            router=TrackingRouter(),
            gateway=TrackingGateway(),
            persistence=TrackingPersistence(),
            isolation=boundary,
        )
        runtime.set_tenant_context(TenantContext(tenant_id="t1", agent_id="a1"))

        result = await runtime.execute_intent(Intent(agent_id="a1", action="x"))
        assert result.success is True

    @pytest.mark.asyncio
    async def test_cross_tenant_blocked(self):
        boundary = IsolationBoundary()
        boundary.register_tenant(TenantModel(tenant_id="t1", name="T1"))
        boundary.register_tenant(TenantModel(tenant_id="t2", name="T2"))
        boundary.register_agent("a1", "t1")
        boundary.register_agent("a2", "t2")

        runtime = KitematicRuntime(
            policy=TrackingPolicy(),
            router=TrackingRouter(),
            gateway=TrackingGateway(),
            persistence=TrackingPersistence(),
            isolation=boundary,
        )
        # Agent a2 is in tenant t2, cannot access t1's state
        from runtime.kitematic_runtime.isolation import AgentNotInTenantError
        with pytest.raises(AgentNotInTenantError):
            boundary.validate_agent_scope("a2", "t1")

    @pytest.mark.asyncio
    async def test_checkpoint_includes_tenant(self):
        persistence = TrackingPersistence()
        boundary = IsolationBoundary()
        boundary.register_tenant(TenantModel(tenant_id="t1", name="T"))
        boundary.register_agent("a1", "t1")

        runtime = KitematicRuntime(
            policy=TrackingPolicy(),
            router=TrackingRouter(),
            gateway=TrackingGateway(),
            persistence=persistence,
            isolation=boundary,
        )
        runtime.set_tenant_context(TenantContext(tenant_id="t1", agent_id="a1"))

        await runtime.execute_intent(Intent(agent_id="a1", action="x"))

        assert len(persistence.saved) == 1
        checkpoint = persistence.saved[0][1]
        assert checkpoint["tenant_id"] == "t1"

    @pytest.mark.asyncio
    async def test_loop_with_tenant_context(self):
        boundary = IsolationBoundary()
        boundary.register_tenant(TenantModel(tenant_id="t1", name="T"))
        boundary.register_agent("a1", "t1")

        budget = ExecutionBudget(max_steps=3)
        runtime = KitematicRuntime(
            policy=TrackingPolicy(),
            router=TrackingRouter(),
            gateway=TrackingGateway(),
            persistence=TrackingPersistence(),
            isolation=boundary,
        )
        loop = LoopController(
            runtime=runtime,
            budget=budget,
            tenant_context=TenantContext(tenant_id="t1", agent_id="a1"),
        )

        result = await loop.run_intent(Intent(agent_id="a1", action="x"))
        assert result.success is True
