"""Integration tests — Checkpoint with Runtime execution."""

from datetime import datetime

import pytest

from core.contracts.step_request import StepRequest
from core.domain.checkpoint import Checkpoint, CheckpointTrigger
from kernel.execution.context import ExecutionContext
from kernel.execution.in_memory import InMemoryRuntime
from infrastructure.storage.checkpoint.in_memory import (
    InMemoryCheckpointRepository,
)


class TestCheckpointRuntimeIntegration:
    @pytest.mark.asyncio
    async def test_save_after_runtime_step(self) -> None:
        repo = InMemoryCheckpointRepository()
        runtime = InMemoryRuntime()
        request = StepRequest(
            execution_id="exec-1",
            agent_id="agent-1",
            goal="test goal",
            state={"value": 1},
        )
        context = ExecutionContext(
            execution_id="exec-1",
            agent_id="agent-1",
            step_number=1,
            state={"value": 1},
            budget_remaining=100,
            tokens_per_step=10,
        )

        await runtime.execute_step(request, context)

        cp = Checkpoint(
            checkpoint_id="cp-1",
            execution_id="exec-1",
            version=1,
            trigger_reason=CheckpointTrigger.STEP_COMPLETE,
            checkpoint_hash="hash1",
            agent_state_ref=None,
            memory_refs=(),
            tool_history=(),
            created_at=datetime(2026, 7, 12, 12, 0, 0),
        )
        await repo.save(cp)

        result = await repo.get("cp-1")
        assert result is not None
        assert result.execution_id == "exec-1"

    @pytest.mark.asyncio
    async def test_restore_checkpoint_state(self) -> None:
        repo = InMemoryCheckpointRepository()

        cp = Checkpoint(
            checkpoint_id="cp-state",
            execution_id="exec-2",
            version=1,
            trigger_reason=CheckpointTrigger.STEP_COMPLETE,
            checkpoint_hash="hash2",
            agent_state_ref=None,
            memory_refs=(),
            tool_history=(),
            created_at=datetime(2026, 7, 12, 12, 0, 0),
        )
        await repo.save(cp)

        restored = await repo.get("cp-state")
        assert restored is not None
        assert restored.checkpoint_id == "cp-state"
        assert restored.version == 1

    @pytest.mark.asyncio
    async def test_multiple_checkpoints_get_latest(self) -> None:
        repo = InMemoryCheckpointRepository()
        for i in range(3):
            cp = Checkpoint(
                checkpoint_id=f"cp-{i}",
                execution_id="exec-3",
                version=i,
                trigger_reason=CheckpointTrigger.STEP_COMPLETE,
                checkpoint_hash=f"hash-{i}",
                agent_state_ref=None,
                memory_refs=(),
                tool_history=(),
                created_at=datetime(2026, 7, 12, 12, i, 0),
            )
            await repo.save(cp)

        latest = await repo.get_latest("exec-3")
        assert latest is not None
        assert latest.version == 2
        assert latest.checkpoint_id == "cp-2"
