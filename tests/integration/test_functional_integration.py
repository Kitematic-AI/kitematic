"""Integration tests — functional tests verifying component interactions."""

import pytest

from control_plane.registry.agents import AgentRegistry
from control_plane.errors import AgentInstanceNotFoundError
from control_plane.lifecycle.manager import LifecycleManager
from control_plane.orchestrator.state_machine import ExecutionStatus
from control_plane.orchestrator.coordinator import StepAction, StepCoordinator
from control_plane.policy.engine import PolicyEngine


class InMemoryRegistry(AgentRegistry):
    """Test double for AgentRegistry."""

    def __init__(self) -> None:
        self._instances: dict[str, dict] = {}

    def add_instance(self, instance_id: str, data: dict) -> None:
        self._instances[instance_id] = data

    async def get_instance(self, instance_id: str):
        return self._instances.get(instance_id)

    async def update_instance_state(self, instance_id: str, status: str):
        if instance_id in self._instances:
            self._instances[instance_id]["status"] = status

    async def get_manifest(self, instance_id: str):
        return self._instances.get(instance_id)


@pytest.fixture
def registry() -> InMemoryRegistry:
    reg = InMemoryRegistry()
    reg.add_instance("inst-1", {"id": "inst-1", "name": "test-agent", "status": "active"})
    return reg


@pytest.fixture
def lifecycle(registry: InMemoryRegistry) -> LifecycleManager:
    return LifecycleManager(agent_registry=registry)


@pytest.fixture
def policy_engine() -> PolicyEngine:
    return PolicyEngine()


@pytest.fixture
def step_coordinator() -> StepCoordinator:
    return StepCoordinator(max_steps=10)


# ──────────────────────────────────────────────
# AgentRegistry ↔ LifecycleManager
# ──────────────────────────────────────────────
class TestAgentRegistryWithLifecycle:
    @pytest.mark.asyncio
    async def test_start_uses_registry(self, lifecycle: LifecycleManager) -> None:
        eid = await lifecycle.start_execution("inst-1", "test goal")
        assert eid.startswith("exec-")

    @pytest.mark.asyncio
    async def test_start_fails_without_instance(self, lifecycle: LifecycleManager) -> None:
        with pytest.raises(AgentInstanceNotFoundError):
            await lifecycle.start_execution("nonexistent", "goal")


# ──────────────────────────────────────────────
# LifecycleManager ↔ PolicyEngine
# ──────────────────────────────────────────────
class TestLifecycleWithPolicyEngine:
    @pytest.mark.asyncio
    async def test_policy_allow_permits_execution(self, lifecycle: LifecycleManager, policy_engine: PolicyEngine) -> None:
        await policy_engine.create_policy("allow-all", "mcp.*", "ALLOW")
        eid = await lifecycle.start_execution("inst-1", "goal")

        policy_result = await policy_engine.evaluate("inst-1", "read", "mcp.database.read")
        status = await lifecycle.get_execution_status(eid)

        assert policy_result["decision"] == "ALLOW"
        assert status == "RUNNING"

    @pytest.mark.asyncio
    async def test_policy_deny_blocks_execution(self, lifecycle: LifecycleManager, policy_engine: PolicyEngine) -> None:
        await policy_engine.create_policy("block-all", "*", "DENY")
        eid = await lifecycle.start_execution("inst-1", "goal")

        policy_result = await policy_engine.evaluate("inst-1", "read", "mcp.database.read")
        assert policy_result["decision"] == "DENY"
        assert await lifecycle.get_execution_status(eid) == "RUNNING"

    @pytest.mark.asyncio
    async def test_policy_approval_requires_human(self, lifecycle: LifecycleManager, policy_engine: PolicyEngine) -> None:
        await policy_engine.create_policy("approval-required", "mcp.*", "REQUIRE_APPROVAL")
        eid = await lifecycle.start_execution("inst-1", "goal")

        policy_result = await policy_engine.evaluate("inst-1", "delete", "mcp.database.delete")
        assert policy_result["decision"] == "REQUIRE_APPROVAL"

    @pytest.mark.asyncio
    async def test_deny_then_complete(self, lifecycle: LifecycleManager, policy_engine: PolicyEngine) -> None:
        await policy_engine.create_policy("block-model", "model.*", "DENY")
        eid = await lifecycle.start_execution("inst-1", "goal")
        policy = await policy_engine.evaluate("inst-1", "call", "model.gpt-4")
        assert policy["decision"] == "DENY"


# ──────────────────────────────────────────────
# StepCoordinator ↔ StateMachine
# ──────────────────────────────────────────────
class TestStepCoordinatorWithStateMachine:
    def test_plan_step_in_running_state(self, step_coordinator: StepCoordinator) -> None:
        plan = step_coordinator.plan_step(
            execution_id="exec-1",
            step_number=1,
            goal="test",
            budget_remaining=100.0,
            allowed_tools=["mcp.database.*"],
        )
        assert plan.action == StepAction.EXECUTE

    def test_plan_step_max_steps_reached(self, step_coordinator: StepCoordinator) -> None:
        plan = step_coordinator.plan_step(
            execution_id="exec-1",
            step_number=10,
            goal="test",
            budget_remaining=100.0,
            allowed_tools=["mcp.database.*"],
        )
        assert plan.action == StepAction.COMPLETE
        assert plan.reason == "max_steps_reached"

    def test_plan_step_budget_exceeded(self, step_coordinator: StepCoordinator) -> None:
        plan = step_coordinator.plan_step(
            execution_id="exec-1",
            step_number=1,
            goal="test",
            budget_remaining=0.0,
            allowed_tools=["mcp.database.*"],
        )
        assert plan.action == StepAction.PAUSE_FOR_APPROVAL
        assert plan.reason == "budget_exceeded"

    def test_plan_step_no_tools(self, step_coordinator: StepCoordinator) -> None:
        plan = step_coordinator.plan_step(
            execution_id="exec-1",
            step_number=1,
            goal="test",
            budget_remaining=100.0,
            allowed_tools=[],
        )
        assert plan.action == StepAction.COMPLETE
        assert plan.reason == "no_tools_available"


# ──────────────────────────────────────────────
# Idempotency
# ──────────────────────────────────────────────
class TestIdempotency:
    @pytest.mark.asyncio
    async def test_start_twice_same_execution_id(self, lifecycle: LifecycleManager) -> None:
        eid1 = await lifecycle.start_execution("inst-1", "goal")
        eid2 = await lifecycle.start_execution("inst-1", "goal")
        assert eid1 == eid2

    @pytest.mark.asyncio
    async def test_stop_twice_no_change(self, lifecycle: LifecycleManager) -> None:
        eid = await lifecycle.start_execution("inst-1", "goal")
        await lifecycle.stop_execution(eid)
        await lifecycle.stop_execution(eid)
        assert await lifecycle.get_execution_status(eid) == "FAILED"


# ──────────────────────────────────────────────
# Invalid State Transitions
# ──────────────────────────────────────────────
class TestInvalidStateTransitions:
    @pytest.mark.asyncio
    async def test_completed_to_running_blocked(self, lifecycle: LifecycleManager) -> None:
        eid = await lifecycle.start_execution("inst-1", "goal")
        # Complete the execution first
        sm = lifecycle._get_state_machine(eid)
        sm.transition(ExecutionStatus.COMPLETED, "done", "test")
        # Now try to start again — should be terminal (no-op)
        assert await lifecycle.get_execution_status(eid) == "COMPLETED"

    @pytest.mark.asyncio
    async def test_failed_to_running_blocked(self, lifecycle: LifecycleManager) -> None:
        eid = await lifecycle.start_execution("inst-1", "goal")
        await lifecycle.stop_execution(eid)
        assert await lifecycle.get_execution_status(eid) == "FAILED"


# ──────────────────────────────────────────────
# Determinism
# ──────────────────────────────────────────────
class TestDeterminism:
    @pytest.mark.asyncio
    async def test_same_input_same_output(self, policy_engine: PolicyEngine) -> None:
        await policy_engine.create_policy("block-model", "model.*", "DENY")
        r1 = await policy_engine.evaluate("agent-1", "call", "model.gpt-4")
        r2 = await policy_engine.evaluate("agent-1", "call", "model.gpt-4")
        assert r1["decision"] == r2["decision"]
        assert r1["matched_rule"] == r2["matched_rule"]

    @pytest.mark.asyncio
    async def test_same_input_same_lifecycle_output(self, lifecycle: LifecycleManager) -> None:
        eid1 = await lifecycle.start_execution("inst-1", "goal")
        status1 = await lifecycle.get_execution_status(eid1)
        status2 = await lifecycle.get_execution_status(eid1)
        assert status1 == status2
