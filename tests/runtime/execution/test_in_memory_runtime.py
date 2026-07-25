"""Unit tests for InMemoryRuntime — step execution engine."""

import pytest

from core.contracts.step_request import StepRequest
from core.contracts.step_response import StepStatus
from runtime.execution.exceptions import (
    BudgetExceededError,
    InvalidStepRequestError,
)
from runtime.execution.execution_context import ExecutionContext
from runtime.execution.execution_runtime import ExecutionRuntime
from runtime.execution.in_memory_runtime import InMemoryRuntime


def _make_request(**overrides) -> StepRequest:
    defaults = dict(
        execution_id="exec-1",
        agent_id="agent-1",
        goal="achieve goal",
        state={"key": "value"},
        allowed_tools=["mcp.*"],
        allowed_models=["gpt-4"],
        max_tokens=50_000,
        max_time_seconds=3600,
    )
    defaults.update(overrides)
    return StepRequest(**defaults)


def _make_context(**overrides) -> ExecutionContext:
    defaults = dict(
        execution_id="exec-1",
        agent_id="agent-1",
        step_number=1,
        state={},
        budget_remaining=1000,
        tokens_per_step=10,
    )
    defaults.update(overrides)
    return ExecutionContext(**defaults)


class TestInMemoryRuntimeImplementsABC:
    def test_isinstance(self) -> None:
        assert isinstance(InMemoryRuntime(), ExecutionRuntime)

    def test_has_execute_step(self) -> None:
        rt = InMemoryRuntime()
        assert hasattr(rt, "execute_step")


class TestExecuteValidStep:
    @pytest.mark.asyncio
    async def test_returns_completed(self) -> None:
        rt = InMemoryRuntime()
        resp = await rt.execute_step(_make_request(), _make_context())
        assert resp.status == StepStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_returns_output(self) -> None:
        rt = InMemoryRuntime()
        resp = await rt.execute_step(_make_request(), _make_context())
        assert "achieve goal" in resp.output

    @pytest.mark.asyncio
    async def test_returns_updated_state(self) -> None:
        rt = InMemoryRuntime()
        resp = await rt.execute_step(_make_request(), _make_context())
        assert "_runtime" in resp.updated_state
        assert resp.updated_state["_runtime"]["steps_executed"] == 1

    @pytest.mark.asyncio
    async def test_tracks_tokens(self) -> None:
        rt = InMemoryRuntime()
        resp = await rt.execute_step(_make_request(), _make_context())
        assert resp.tokens_consumed == 10


class TestBudgetExhausted:
    @pytest.mark.asyncio
    async def test_budget_zero_raises(self) -> None:
        rt = InMemoryRuntime()
        with pytest.raises(BudgetExceededError):
            await rt.execute_step(_make_request(), _make_context(budget_remaining=0))

    @pytest.mark.asyncio
    async def test_budget_negative_raises(self) -> None:
        rt = InMemoryRuntime()
        with pytest.raises(BudgetExceededError):
            await rt.execute_step(_make_request(), _make_context(budget_remaining=-5))


class TestInvalidRequest:
    @pytest.mark.asyncio
    async def test_missing_execution_id(self) -> None:
        rt = InMemoryRuntime()
        req = _make_request(execution_id="")
        with pytest.raises(InvalidStepRequestError) as exc_info:
            await rt.execute_step(req, _make_context())
        assert "execution_id" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_missing_goal(self) -> None:
        rt = InMemoryRuntime()
        req = _make_request(goal="")
        with pytest.raises(InvalidStepRequestError) as exc_info:
            await rt.execute_step(req, _make_context())
        assert "goal" in str(exc_info.value)


class TestDeterminism:
    @pytest.mark.asyncio
    async def test_same_input_same_output(self) -> None:
        rt = InMemoryRuntime()
        req = _make_request()
        ctx = _make_context()
        r1 = await rt.execute_step(req, ctx)
        r2 = await rt.execute_step(req, ctx)
        assert r1.status == r2.status
        assert r1.output == r2.output


class TestMultipleSteps:
    @pytest.mark.asyncio
    async def test_step_number_increments(self) -> None:
        rt = InMemoryRuntime()
        req = _make_request()
        r1 = await rt.execute_step(req, _make_context(step_number=1))
        r2 = await rt.execute_step(req, _make_context(step_number=2))
        assert r1.updated_state["_runtime"]["last_node"] == "step-1"
        assert r2.updated_state["_runtime"]["last_node"] == "step-2"


class TestNoInputMutation:
    @pytest.mark.asyncio
    async def test_input_state_not_mutated(self) -> None:
        rt = InMemoryRuntime()
        state = {"key": "original"}
        req = _make_request(state=state)
        await rt.execute_step(req, _make_context())
        assert state.get("_runtime") is None
