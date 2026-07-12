"""Unit tests for RuntimeExecutorAdapter."""

import copy
from typing import Any
from unittest.mock import AsyncMock

import pytest

from runtime.contracts.step_response import StepResponse, StepStatus
from runtime.execution.execution_runtime import ExecutionRuntime
from runtime.execution.in_memory_runtime import InMemoryRuntime
from services.control_plane.adapters.runtime_adapter import RuntimeExecutorAdapter
from services.control_plane.orchestrator.step_coordinator import StepCoordinator, StepAction, StepPlan
from services.control_plane.orchestrator.state_machine import ExecutionStateMachine, ExecutionStatus


def _make_context(**overrides) -> dict[str, Any]:
    defaults = dict(
        execution_id="exec-1",
        agent_id="agent-1",
        goal="achieve goal",
        step_number=1,
        state={"key": "value"},
        budget_remaining=100.0,
        allowed_tools=["mcp.*"],
    )
    defaults.update(overrides)
    return defaults


class TestPlanAndExecute:
    @pytest.mark.asyncio
    async def test_returns_execute_and_response_on_success(self) -> None:
        rt = InMemoryRuntime()
        adapter = RuntimeExecutorAdapter(runtime=rt)
        sm = ExecutionStateMachine()
        sm.transition(ExecutionStatus.RUNNING, "started", "test")

        plan, resp = await adapter.plan_and_execute(**_make_context(), sm=sm)

        assert plan.action == StepAction.EXECUTE
        assert resp is not None
        assert resp.status == StepStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_returns_pause_and_none_on_budget_exceeded(self) -> None:
        rt = InMemoryRuntime()
        adapter = RuntimeExecutorAdapter(runtime=rt)
        sm = ExecutionStateMachine()

        plan, resp = await adapter.plan_and_execute(
            **_make_context(budget_remaining=0.0), sm=sm
        )

        assert plan.action == StepAction.PAUSE_FOR_APPROVAL
        assert resp is None

    @pytest.mark.asyncio
    async def test_returns_complete_and_none_on_max_steps(self) -> None:
        rt = InMemoryRuntime()
        coordinator = StepCoordinator(max_steps=1)
        adapter = RuntimeExecutorAdapter(runtime=rt, coordinator=coordinator)
        sm = ExecutionStateMachine()

        plan, resp = await adapter.plan_and_execute(
            **_make_context(step_number=1), sm=sm
        )

        assert plan.action == StepAction.COMPLETE
        assert resp is None

    @pytest.mark.asyncio
    async def test_returns_complete_and_none_on_no_tools(self) -> None:
        rt = InMemoryRuntime()
        adapter = RuntimeExecutorAdapter(runtime=rt)
        sm = ExecutionStateMachine()

        plan, resp = await adapter.plan_and_execute(
            **_make_context(allowed_tools=[]), sm=sm
        )

        assert plan.action == StepAction.COMPLETE
        assert resp is None


class TestStateMachineIntegration:
    @pytest.mark.asyncio
    async def test_transits_to_failed_on_runtime_failure(self) -> None:
        class FailingRuntime(ExecutionRuntime):
            async def execute_step(self, request, context):
                raise RuntimeError("boom")

        adapter = RuntimeExecutorAdapter(runtime=FailingRuntime())
        sm = ExecutionStateMachine()
        sm.transition(ExecutionStatus.RUNNING, "started", "test")

        resp = await adapter.execute_step(**_make_context(), sm=sm)

        assert resp.status == StepStatus.FAILED
        assert "boom" in resp.error_message
        assert sm.current_state == ExecutionStatus.FAILED

    @pytest.mark.asyncio
    async def test_does_not_transit_sm_on_success(self) -> None:
        rt = InMemoryRuntime()
        adapter = RuntimeExecutorAdapter(runtime=rt)
        sm = ExecutionStateMachine()
        sm.transition(ExecutionStatus.RUNNING, "started", "test")

        await adapter.execute_step(**_make_context(), sm=sm)

        assert sm.current_state == ExecutionStatus.RUNNING

    @pytest.mark.asyncio
    async def test_returns_step_response_on_exception(self) -> None:
        class ErrorRuntime(ExecutionRuntime):
            async def execute_step(self, request, context):
                raise ValueError("internal error")

        adapter = RuntimeExecutorAdapter(runtime=ErrorRuntime())
        sm = ExecutionStateMachine()
        sm.transition(ExecutionStatus.RUNNING, "started", "test")

        resp = await adapter.execute_step(**_make_context(), sm=sm)

        assert resp.status == StepStatus.FAILED
        assert "internal error" in resp.error_message


class TestContextBuilding:
    @pytest.mark.asyncio
    async def test_passes_memory_to_context(self) -> None:
        class FakeMemory:
            pass

        mem = FakeMemory()
        rt = InMemoryRuntime()
        adapter = RuntimeExecutorAdapter(runtime=rt, memory=mem)
        sm = ExecutionStateMachine()
        sm.transition(ExecutionStatus.RUNNING, "started", "test")

        resp = await adapter.execute_step(**_make_context(), sm=sm)

        assert resp.status == StepStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_passes_checkpoint_to_context(self) -> None:
        class FakeCheckpoint:
            async def save(self, cp):
                return cp

        cp = FakeCheckpoint()
        rt = InMemoryRuntime()
        adapter = RuntimeExecutorAdapter(runtime=rt, checkpoint=cp)
        sm = ExecutionStateMachine()
        sm.transition(ExecutionStatus.RUNNING, "started", "test")

        resp = await adapter.execute_step(**_make_context(), sm=sm)

        assert resp.status == StepStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_works_without_optional_repos(self) -> None:
        rt = InMemoryRuntime()
        adapter = RuntimeExecutorAdapter(runtime=rt)
        sm = ExecutionStateMachine()
        sm.transition(ExecutionStatus.RUNNING, "started", "test")

        resp = await adapter.execute_step(**_make_context(), sm=sm)

        assert resp.status == StepStatus.COMPLETED


class TestDeterminism:
    @pytest.mark.asyncio
    async def test_same_inputs_same_output(self) -> None:
        rt = InMemoryRuntime()
        adapter = RuntimeExecutorAdapter(runtime=rt)
        sm = ExecutionStateMachine()
        sm.transition(ExecutionStatus.RUNNING, "started", "test")

        ctx = _make_context()
        r1 = await adapter.execute_step(**ctx, sm=sm)
        sm._current_state = ExecutionStatus.RUNNING  # reset for next call
        r2 = await adapter.execute_step(**ctx, sm=sm)

        assert r1.status == r2.status
        assert r1.output == r2.output


class TestInputStateMutation:
    @pytest.mark.asyncio
    async def test_adapter_does_not_mutate_input_state(self) -> None:
        rt = InMemoryRuntime()
        adapter = RuntimeExecutorAdapter(runtime=rt)
        sm = ExecutionStateMachine()
        sm.transition(ExecutionStatus.RUNNING, "started", "test")

        original_state = {"key": "value", "nested": {"x": 1}}
        state_copy = copy.deepcopy(original_state)

        await adapter.execute_step(
            **_make_context(state=original_state), sm=sm
        )

        assert original_state == state_copy

    @pytest.mark.asyncio
    async def test_coordinator_dependency_injection_works(self) -> None:
        class CustomCoordinator:
            def plan_step(self, execution_id, step_number, goal, budget, tools):
                from services.control_plane.orchestrator.step_coordinator import StepPlan
                return StepPlan(
                    action=StepAction.EXECUTE,
                    execution_id=execution_id,
                    step_number=step_number,
                    reason="custom",
                )

        rt = InMemoryRuntime()
        adapter = RuntimeExecutorAdapter(runtime=rt, coordinator=CustomCoordinator())
        sm = ExecutionStateMachine()
        sm.transition(ExecutionStatus.RUNNING, "started", "test")

        plan, resp = await adapter.plan_and_execute(**_make_context(), sm=sm)

        assert plan.action == StepAction.EXECUTE
        assert plan.reason == "custom"
        assert resp is not None

    @pytest.mark.asyncio
    async def test_runtime_exception_converted_to_step_response(self) -> None:
        class CrashRuntime(ExecutionRuntime):
            async def execute_step(self, request, context):
                raise RuntimeError("crash")

        adapter = RuntimeExecutorAdapter(runtime=CrashRuntime())
        sm = ExecutionStateMachine()
        sm.transition(ExecutionStatus.RUNNING, "started", "test")

        resp = await adapter.execute_step(**_make_context(), sm=sm)

        assert resp.status == StepStatus.FAILED
        assert resp.tokens_consumed == 0
