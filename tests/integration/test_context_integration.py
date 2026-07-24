"""Integration tests — ExecutionContext expansion with services."""


import pytest

from runtime.contracts.step_request import StepRequest
from runtime.execution.context_builder import ContextBuilder
from runtime.execution.execution_context import ExecutionContext
from runtime.execution.in_memory_runtime import InMemoryRuntime
from services.checkpoint.repositories.in_memory_checkpoint import (
    InMemoryCheckpointRepository,
)
from services.memory.repositories.in_memory_memory import InMemoryMemoryRepository


class TestRuntimeCheckpointMemoryIntegration:
    @pytest.mark.asyncio
    async def test_runtime_checkpoint_memory_together(self) -> None:
        cp_repo = InMemoryCheckpointRepository()
        mem_repo = InMemoryMemoryRepository()

        ctx = (
            ContextBuilder("exec-1", "agent-1")
            .with_budget(100)
            .with_step_number(1)
            .with_state({})
            .with_checkpoint(cp_repo)
            .with_memory(mem_repo)
            .build()
        )

        rt = InMemoryRuntime()
        req = StepRequest(
            execution_id="exec-1",
            agent_id="agent-1",
            goal="compute",
            state={},
        )

        await rt.execute_step(req, ctx)

        checkpoints = await cp_repo.list_by_execution("exec-1")
        assert len(checkpoints) == 1

        # memory is injectable via context
        assert ctx.memory is mem_repo

    @pytest.mark.asyncio
    async def test_multiple_steps_checkpoint_each(self) -> None:
        cp_repo = InMemoryCheckpointRepository()
        rt = InMemoryRuntime()
        req = StepRequest(
            execution_id="exec-2",
            agent_id="agent-1",
            goal="multi-step",
            state={},
        )

        for step in range(1, 4):
            ctx = ExecutionContext(
                execution_id="exec-2",
                agent_id="agent-1",
                step_number=step,
                state={},
                budget_remaining=100,
                tokens_per_step=10,
                checkpoint=cp_repo,
            )
            await rt.execute_step(req, ctx)

        checkpoints = await cp_repo.list_by_execution("exec-2")
        assert len(checkpoints) == 3
        versions = sorted(cp.version for cp in checkpoints)
        assert versions == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_context_preserved_across_steps(self) -> None:
        ctx = (
            ContextBuilder("exec-3", "agent-1")
            .with_budget(100)
            .with_step_number(1)
            .with_state({"counter": 0})
            .build()
        )

        rt = InMemoryRuntime()
        req = StepRequest(
            execution_id="exec-3",
            agent_id="agent-1",
            goal="preserve context",
            state=ctx.state,
        )

        resp1 = await rt.execute_step(req, ctx)
        assert ctx.tokens_consumed == 10
        assert ctx.budget_remaining == 90
