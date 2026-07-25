"""Unit tests for InMemoryCheckpointRepository."""

from datetime import datetime
from uuid import uuid4

import pytest

from core.domain.checkpoint import Checkpoint, CheckpointTrigger
from services.checkpoint.repositories.in_memory_checkpoint import (
    InMemoryCheckpointRepository,
)


def _make_checkpoint(
    execution_id: str = "exec-1",
    version: int = 0,
    trigger: CheckpointTrigger = CheckpointTrigger.STEP_COMPLETE,
) -> Checkpoint:
    return Checkpoint(
        checkpoint_id=str(uuid4()),
        execution_id=execution_id,
        version=version,
        trigger_reason=trigger,
        checkpoint_hash="hash",
        agent_state_ref="ref",
        memory_refs=(),
        tool_history=(),
        created_at=datetime(2026, 7, 12, 12, 0, 0),
    )


class TestCheckpointRepositorySaveAndGet:
    @pytest.mark.asyncio
    async def test_save_and_get_roundtrip(self) -> None:
        repo = InMemoryCheckpointRepository()
        cp = _make_checkpoint(execution_id="exec-1", version=0)
        cp_id = cp.checkpoint_id

        await repo.save(cp)
        result = await repo.get(cp_id)

        assert result is not None
        assert result.checkpoint_id == cp_id
        assert result.execution_id == "exec-1"
        assert result.version == 0
        assert result.trigger_reason == CheckpointTrigger.STEP_COMPLETE

    @pytest.mark.asyncio
    async def test_get_returns_none_for_unknown_id(self) -> None:
        repo = InMemoryCheckpointRepository()
        result = await repo.get("nonexistent-id")
        assert result is None


class TestCheckpointRepositoryList:
    @pytest.mark.asyncio
    async def test_list_by_execution_returns_checkpoints(self) -> None:
        repo = InMemoryCheckpointRepository()
        cp1 = _make_checkpoint(execution_id="exec-1", version=0)
        cp2 = _make_checkpoint(execution_id="exec-1", version=1)
        cp3 = _make_checkpoint(execution_id="exec-2", version=0)
        await repo.save(cp1)
        await repo.save(cp2)
        await repo.save(cp3)

        result = await repo.list_by_execution("exec-1")
        assert len(result) == 2
        assert all(cp.execution_id == "exec-1" for cp in result)

    @pytest.mark.asyncio
    async def test_list_by_execution_returns_empty_for_unknown(self) -> None:
        repo = InMemoryCheckpointRepository()
        result = await repo.list_by_execution("nonexistent-exec")
        assert result == []


class TestCheckpointRepositoryLatest:
    @pytest.mark.asyncio
    async def test_get_latest_returns_highest_version(self) -> None:
        repo = InMemoryCheckpointRepository()
        cp1 = _make_checkpoint(execution_id="exec-1", version=0)
        cp2 = _make_checkpoint(execution_id="exec-1", version=2)
        cp3 = _make_checkpoint(execution_id="exec-1", version=1)
        await repo.save(cp1)
        await repo.save(cp2)
        await repo.save(cp3)

        result = await repo.get_latest("exec-1")
        assert result is not None
        assert result.version == 2
        assert result.checkpoint_id == cp2.checkpoint_id

    @pytest.mark.asyncio
    async def test_get_latest_returns_none_for_unknown(self) -> None:
        repo = InMemoryCheckpointRepository()
        result = await repo.get_latest("nonexistent-exec")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_latest_not_rely_on_insertion_order(self) -> None:
        repo = InMemoryCheckpointRepository()
        cp5 = _make_checkpoint(execution_id="exec-1", version=5)
        cp1 = _make_checkpoint(execution_id="exec-1", version=1)
        cp3 = _make_checkpoint(execution_id="exec-1", version=3)
        await repo.save(cp5)
        await repo.save(cp1)
        await repo.save(cp3)

        result = await repo.get_latest("exec-1")
        assert result is not None
        assert result.version == 5
        assert result.checkpoint_id == cp5.checkpoint_id


class TestCheckpointRepositoryImmutability:
    @pytest.mark.asyncio
    async def test_save_immutable(self) -> None:
        repo = InMemoryCheckpointRepository()
        cp = _make_checkpoint(execution_id="exec-1", version=0)
        cp_id = cp.checkpoint_id
        await repo.save(cp)

        object.__setattr__(cp, "version", 999)
        stored = await repo.get(cp_id)
        assert stored is not None
        assert stored.version == 0

    @pytest.mark.asyncio
    async def test_get_returns_copy(self) -> None:
        repo = InMemoryCheckpointRepository()
        cp = _make_checkpoint(execution_id="exec-1", version=0)
        cp_id = cp.checkpoint_id
        await repo.save(cp)

        returned = await repo.get(cp_id)
        assert returned is not None
        object.__setattr__(returned, "version", 999)

        stored = await repo.get(cp_id)
        assert stored is not None
        assert stored.version == 0

    @pytest.mark.asyncio
    async def test_list_ordered_by_version(self) -> None:
        repo = InMemoryCheckpointRepository()
        cp3 = _make_checkpoint(execution_id="exec-1", version=3)
        cp1 = _make_checkpoint(execution_id="exec-1", version=1)
        cp2 = _make_checkpoint(execution_id="exec-1", version=2)
        await repo.save(cp3)
        await repo.save(cp1)
        await repo.save(cp2)

        result = await repo.list_by_execution("exec-1")
        versions = [cp.version for cp in result]
        assert versions == [1, 2, 3]
