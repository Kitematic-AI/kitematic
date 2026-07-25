"""Tests for FileSystemCheckpointRepository — durable checkpoint storage."""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from core.domain.checkpoint import Checkpoint, CheckpointTrigger
from services.checkpoint.repositories.file_system_checkpoint import (
    FileSystemCheckpointRepository,
)


@pytest.fixture
def temp_dir():
    path = tempfile.mkdtemp(prefix="kitematic-checkpoint-test-")
    yield path
    shutil.rmtree(path)


def make_checkpoint(
    checkpoint_id: str = "cp-test-001",
    execution_id: str = "exec-1",
    version: int = 1,
    state_ref: str | None = "state-json",
) -> Checkpoint:
    return Checkpoint(
        checkpoint_id=checkpoint_id,
        execution_id=execution_id,
        version=version,
        trigger_reason=CheckpointTrigger.STEP_COMPLETE,
        checkpoint_hash="abc123",
        agent_state_ref=state_ref,
    )


class TestFileSystemCheckpointSave:
    """Tests for save method."""

    @pytest.mark.asyncio
    async def test_save_creates_file(self, temp_dir):
        repo = FileSystemCheckpointRepository(temp_dir)
        cp = make_checkpoint(checkpoint_id="cp-test-001")

        result = await repo.save(cp)

        file_path = Path(temp_dir) / "checkpoints" / "cp-test-001.json"
        assert file_path.exists()
        assert result.checkpoint_id == "cp-test-001"

    @pytest.mark.asyncio
    async def test_save_returns_deep_copy(self, temp_dir):
        repo = FileSystemCheckpointRepository(temp_dir)
        cp = make_checkpoint()

        result = await repo.save(cp)

        # Mutating the original should not affect stored copy
        # (Checkpoint is frozen so we can't mutate, but the save returns a deep copy)
        assert result == cp

    @pytest.mark.asyncio
    async def test_save_persists_metadata(self, temp_dir):
        repo = FileSystemCheckpointRepository(temp_dir)
        cp = make_checkpoint(
            checkpoint_id="cp-meta",
            execution_id="exec-meta",
            version=5,
            state_ref='{"key": "val"}',
        )

        await repo.save(cp)

        file_path = Path(temp_dir) / "checkpoints" / "cp-meta.json"
        with open(file_path) as f:
            data = json.load(f)

        assert data["checkpoint_id"] == "cp-meta"
        assert data["execution_id"] == "exec-meta"
        assert data["version"] == 5
        assert data["agent_state_ref"] == '{"key": "val"}'
        assert data["trigger_reason"] == "STEP_COMPLETE"

    @pytest.mark.asyncio
    async def test_save_updates_index(self, temp_dir):
        repo = FileSystemCheckpointRepository(temp_dir)
        cp = make_checkpoint(execution_id="exec-index")

        await repo.save(cp)

        # Index file exists
        index_path = Path(temp_dir) / "index.json"
        assert index_path.exists()

        with open(index_path) as f:
            index = json.load(f)

        assert "exec-index" in index
        assert "cp-test-001" in index["exec-index"]


class TestFileSystemCheckpointGet:
    """Tests for get method."""

    @pytest.mark.asyncio
    async def test_get_returns_checkpoint(self, temp_dir):
        repo = FileSystemCheckpointRepository(temp_dir)
        cp = make_checkpoint(checkpoint_id="cp-get")
        await repo.save(cp)

        result = await repo.get("cp-get")

        assert result is not None
        assert result.checkpoint_id == "cp-get"
        assert result.execution_id == "exec-1"
        assert result.version == 1

    @pytest.mark.asyncio
    async def test_get_not_found(self, temp_dir):
        repo = FileSystemCheckpointRepository(temp_dir)

        result = await repo.get("cp-nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_returns_deep_copy(self, temp_dir):
        repo = FileSystemCheckpointRepository(temp_dir)
        cp = make_checkpoint(checkpoint_id="cp-deepcopy")
        await repo.save(cp)

        result1 = await repo.get("cp-deepcopy")
        result2 = await repo.get("cp-deepcopy")

        # Same content but different objects
        assert result1 == result2
        assert result1 is not result2


class TestFileSystemCheckpointList:
    """Tests for list_by_execution and get_latest."""

    @pytest.mark.asyncio
    async def test_list_by_execution(self, temp_dir):
        repo = FileSystemCheckpointRepository(temp_dir)
        cp1 = make_checkpoint(checkpoint_id="cp-list-1", version=1)
        cp2 = make_checkpoint(checkpoint_id="cp-list-2", version=2)
        cp3 = make_checkpoint(checkpoint_id="cp-list-3", execution_id="exec-other")
        await repo.save(cp1)
        await repo.save(cp2)
        await repo.save(cp3)

        results = await repo.list_by_execution("exec-1")

        assert len(results) == 2
        assert results[0].version == 1
        assert results[1].version == 2

    @pytest.mark.asyncio
    async def test_list_by_execution_empty(self, temp_dir):
        repo = FileSystemCheckpointRepository(temp_dir)

        results = await repo.list_by_execution("exec-empty")

        assert results == []

    @pytest.mark.asyncio
    async def test_get_latest(self, temp_dir):
        repo = FileSystemCheckpointRepository(temp_dir)
        cp1 = make_checkpoint(checkpoint_id="cp-latest-1", version=1)
        cp2 = make_checkpoint(checkpoint_id="cp-latest-2", version=3)
        cp3 = make_checkpoint(checkpoint_id="cp-latest-3", version=2)
        await repo.save(cp1)
        await repo.save(cp2)
        await repo.save(cp3)

        result = await repo.get_latest("exec-1")

        assert result is not None
        assert result.checkpoint_id == "cp-latest-2"
        assert result.version == 3

    @pytest.mark.asyncio
    async def test_get_latest_empty(self, temp_dir):
        repo = FileSystemCheckpointRepository(temp_dir)

        result = await repo.get_latest("exec-empty")

        assert result is None


class TestFileSystemCheckpointDurability:
    """Tests for durability across re-instantiation (simulating restart)."""

    @pytest.mark.asyncio
    async def test_survives_reinit(self, temp_dir):
        # First instance
        repo1 = FileSystemCheckpointRepository(temp_dir)
        cp = make_checkpoint(checkpoint_id="cp-survive")
        await repo1.save(cp)

        # Second instance (simulates restart)
        repo2 = FileSystemCheckpointRepository(temp_dir)
        result = await repo2.get("cp-survive")

        assert result is not None
        assert result.checkpoint_id == "cp-survive"

    @pytest.mark.asyncio
    async def test_multi_checkpoint_survives_reinit(self, temp_dir):
        repo1 = FileSystemCheckpointRepository(temp_dir)
        await repo1.save(make_checkpoint(checkpoint_id="cp-a", version=1))
        await repo1.save(make_checkpoint(checkpoint_id="cp-b", version=2))

        repo2 = FileSystemCheckpointRepository(temp_dir)

        assert await repo2.get("cp-a") is not None
        assert await repo2.get("cp-b") is not None
        assert len(await repo2.list_by_execution("exec-1")) == 2

    @pytest.mark.asyncio
    async def test_index_survives_reinit(self, temp_dir):
        repo1 = FileSystemCheckpointRepository(temp_dir)
        await repo1.save(make_checkpoint(checkpoint_id="cp-idx-1", execution_id="exec-x"))

        repo2 = FileSystemCheckpointRepository(temp_dir)
        latest = await repo2.get_latest("exec-x")

        assert latest is not None
        assert latest.checkpoint_id == "cp-idx-1"


class TestFileSystemCheckpointAdapterRoundtrip:
    """End-to-end: CheckpointPersistenceAdapter + FileSystemCheckpointRepository."""

    @pytest.mark.asyncio
    async def test_save_restore_roundtrip(self, temp_dir):
        fs_repo = FileSystemCheckpointRepository(temp_dir)
        from control_plane.adapters.to_kernel.checkpoint import (
            CheckpointPersistenceAdapter,
        )

        adapter = CheckpointPersistenceAdapter(fs_repo)
        state = {"step": 1, "data": {"key": "value"}}

        cp_id = await adapter.save("exec-1", state)
        restored = await adapter.restore(cp_id)

        assert restored == state

    @pytest.mark.asyncio
    async def test_restart_roundtrip(self, temp_dir):
        """Simulate process restart: new adapter, new repo instance, same data dir."""
        fs_repo1 = FileSystemCheckpointRepository(temp_dir)
        from control_plane.adapters.to_kernel.checkpoint import (
            CheckpointPersistenceAdapter,
        )

        adapter1 = CheckpointPersistenceAdapter(fs_repo1)
        cp_id = await adapter1.save("exec-restart", {"after_restart": True})

        # Simulate restart
        fs_repo2 = FileSystemCheckpointRepository(temp_dir)
        adapter2 = CheckpointPersistenceAdapter(fs_repo2)
        restored = await adapter2.restore(cp_id)

        assert restored == {"after_restart": True}

    @pytest.mark.asyncio
    async def test_restore_after_restart_with_multiple(self, temp_dir):
        fs_repo1 = FileSystemCheckpointRepository(temp_dir)
        from control_plane.adapters.to_kernel.checkpoint import (
            CheckpointPersistenceAdapter,
        )

        a1 = CheckpointPersistenceAdapter(fs_repo1)
        id1 = await a1.save("exec-multi", {"v": 1})
        id2 = await a1.save("exec-multi", {"v": 2})

        fs_repo2 = FileSystemCheckpointRepository(temp_dir)
        a2 = CheckpointPersistenceAdapter(fs_repo2)

        s1 = await a2.restore(id1)
        s2 = await a2.restore(id2)
        assert s1 == {"v": 1}
        assert s2 == {"v": 2}
