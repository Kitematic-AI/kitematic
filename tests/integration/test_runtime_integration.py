"""Integration tests — Runtime Engine with Control Plane components."""

import pytest

from core.contracts.step_request import StepRequest
from core.contracts.step_response import StepStatus
from kernel.execution.context import ExecutionContext
from kernel.execution.in_memory import InMemoryRuntime
from control_plane.orchestrator.state_machine import ExecutionStateMachine, ExecutionStatus
from control_plane.orchestrator.coordinator import StepAction, StepCoordinator
from control_plane.policy.engine import PolicyEngine


@pytest.fixture
def runtime() -> InMemoryRuntime:
    return InMemoryRuntime()


@pytest.fixture
def coordinator() -> StepCoordinator:
    return StepCoordinator(max_steps=10)


@pytest.fixture
def policy_engine() -> PolicyEngine:
    return PolicyEngine()


class TestRuntimeWithStepCoordinator:
    @pytest.mark.asyncio
    async def test_plan_then_execute(self, runtime: InMemoryRuntime, coordinator: StepCoordinator) -> None:
        plan = coordinator.plan_step("exec-1", 1, "goal", 100.0, ["mcp.*"])
        assert plan.action == StepAction.EXECUTE

        req = StepRequest(
            execution_id="exec-1",
            agent_id="agent-1",
            goal="goal",
            state={},
            allowed_tools=["mcp.*"],
        )
        ctx = ExecutionContext(
            execution_id="exec-1",
            agent_id="agent-1",
            step_number=1,
            state={},
            budget_remaining=100,
        )
        resp = await runtime.execute_step(req, ctx)
        assert resp.status == StepStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_plan_budget_exceeded_then_pause(self, coordinator: StepCoordinator) -> None:
        plan = coordinator.plan_step("exec-1", 1, "goal", 0.0, ["mcp.*"])
        assert plan.action == StepAction.PAUSE_FOR_APPROVAL


class TestRuntimeWithPolicy:
    @pytest.mark.asyncio
    async def test_policy_allow_then_execute(self, runtime: InMemoryRuntime, policy_engine: PolicyEngine) -> None:
        await policy_engine.create_policy("allow-all", "mcp.*", "ALLOW")
        decision = await policy_engine.evaluate("agent-1", "read", "mcp.database.read")
        assert decision["decision"] == "ALLOW"

        req = StepRequest(
            execution_id="exec-1",
            agent_id="agent-1",
            goal="read data",
            state={},
            allowed_tools=["mcp.*"],
        )
        ctx = ExecutionContext(
            execution_id="exec-1",
            agent_id="agent-1",
            step_number=1,
            state={},
            budget_remaining=100,
        )
        resp = await runtime.execute_step(req, ctx)
        assert resp.status == StepStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_policy_deny_then_no_execute(self, policy_engine: PolicyEngine) -> None:
        await policy_engine.create_policy("block-all", "mcp.*", "DENY")
        decision = await policy_engine.evaluate("agent-1", "read", "mcp.database.read")
        assert decision["decision"] == "DENY"


class TestRuntimeDoesNotMutateStateMachine:
    @pytest.mark.asyncio
    async def test_runtime_does_not_transition(self, runtime: InMemoryRuntime) -> None:
        sm = ExecutionStateMachine()
        assert sm.current_state == ExecutionStatus.PENDING

        req = StepRequest(
            execution_id="exec-1",
            agent_id="agent-1",
            goal="goal",
            state={},
            allowed_tools=["mcp.*"],
        )
        ctx = ExecutionContext(
            execution_id="exec-1",
            agent_id="agent-1",
            step_number=1,
            state={},
            budget_remaining=100,
        )
        await runtime.execute_step(req, ctx)
        assert sm.current_state == ExecutionStatus.PENDING
