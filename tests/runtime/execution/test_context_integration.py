"""Unit tests for InMemoryRuntime + ExecutionContext integration."""

import pytest

from core.contracts.step_request import StepRequest
from core.contracts.step_response import StepStatus
from kernel.execution.context_builder import ContextBuilder
from kernel.execution.context import ExecutionContext
from kernel.execution.in_memory import InMemoryRuntime
from infrastructure.storage.checkpoint.in_memory import (
    InMemoryCheckpointRepository,
)


class TestRuntimeTokenTracking:
    @pytest.mark.asyncio
    async def test_tokens_consumed_accumulates(self) -> None:
        rt = InMemoryRuntime()
        req = StepRequest(
            execution_id="exec-1",
            agent_id="agent-1",
            goal="goal",
            state={},
        )
        ctx = ExecutionContext(
            execution_id="exec-1",
            agent_id="agent-1",
            step_number=1,
            state={},
            budget_remaining=100,
            tokens_per_step=10,
        )

        await rt.execute_step(req, ctx)
        assert ctx.tokens_consumed == 10
        assert ctx.budget_remaining == 90

        ctx2 = ExecutionContext(
            execution_id="exec-1",
            agent_id="agent-1",
            step_number=2,
            state={},
            budget_remaining=90,
            tokens_per_step=10,
        )
        await rt.execute_step(req, ctx2)
        assert ctx2.tokens_consumed == 10
        assert ctx2.budget_remaining == 80

    @pytest.mark.asyncio
    async def test_budget_remaining_decreases(self) -> None:
        rt = InMemoryRuntime()
        req = StepRequest(
            execution_id="exec-1",
            agent_id="agent-1",
            goal="goal",
            state={},
        )
        ctx = ExecutionContext(
            execution_id="exec-1",
            agent_id="agent-1",
            step_number=1,
            state={},
            budget_remaining=100,
            tokens_per_step=25,
        )

        resp = await rt.execute_step(req, ctx)
        assert ctx.budget_remaining == 75
        assert resp.tokens_consumed == 25


class TestRuntimeCheckpointIntegration:
    @pytest.mark.asyncio
    async def test_checkpoint_saved_after_step(self) -> None:
        repo = InMemoryCheckpointRepository()
        rt = InMemoryRuntime()
        req = StepRequest(
            execution_id="exec-1",
            agent_id="agent-1",
            goal="goal",
            state={},
        )
        ctx = ExecutionContext(
            execution_id="exec-1",
            agent_id="agent-1",
            step_number=1,
            state={},
            budget_remaining=100,
            tokens_per_step=10,
            checkpoint=repo,
        )

        await rt.execute_step(req, ctx)

        checkpoints = await repo.list_by_execution("exec-1")
        assert len(checkpoints) == 1
        assert checkpoints[0].version == 1
        assert checkpoints[0].execution_id == "exec-1"

    @pytest.mark.asyncio
    async def test_no_checkpoint_when_none(self) -> None:
        rt = InMemoryRuntime()
        req = StepRequest(
            execution_id="exec-1",
            agent_id="agent-1",
            goal="goal",
            state={},
        )
        ctx = ExecutionContext(
            execution_id="exec-1",
            agent_id="agent-1",
            step_number=1,
            state={},
            budget_remaining=100,
            tokens_per_step=10,
            checkpoint=None,
        )

        resp = await rt.execute_step(req, ctx)
        assert resp.status == StepStatus.COMPLETED


class TestRuntimeContextBuilder:
    @pytest.mark.asyncio
    async def test_context_builder_with_runtime(self) -> None:
        rt = InMemoryRuntime()
        ctx = (
            ContextBuilder("exec-1", "agent-1")
            .with_budget(100)
            .with_step_number(1)
            .with_state({"x": 1})
            .build()
        )
        req = StepRequest(
            execution_id="exec-1",
            agent_id="agent-1",
            goal="goal",
            state=ctx.state,
        )
        resp = await rt.execute_step(req, ctx)
        assert resp.status == StepStatus.COMPLETED
        assert ctx.tokens_consumed == 10
