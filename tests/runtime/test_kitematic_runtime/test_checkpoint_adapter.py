"""Tests for CheckpointPersistenceAdapter — ABI StatePersistence → CheckpointRepository."""


import pytest

from core.domain.checkpoint import Checkpoint, CheckpointTrigger
from control_plane.adapters.to_kernel.checkpoint import CheckpointPersistenceAdapter
from kernel.exceptions import CheckpointPersistenceError


class MockCheckpointRepository:
    """Mock CheckpointRepository for testing."""

    def __init__(self):
        self._store: dict[str, Checkpoint] = {}

    async def save(self, checkpoint: Checkpoint) -> Checkpoint:
        self._store[checkpoint.checkpoint_id] = checkpoint
        return checkpoint

    async def get(self, checkpoint_id: str) -> Checkpoint | None:
        return self._store.get(checkpoint_id)

    async def list_by_execution(self, execution_id: str) -> list[Checkpoint]:
        return [c for c in self._store.values() if c.execution_id == execution_id]

    async def get_latest(self, execution_id: str) -> Checkpoint | None:
        matching = [c for c in self._store.values() if c.execution_id == execution_id]
        if not matching:
            return None
        return max(matching, key=lambda c: c.version)


class TestCheckpointPersistenceAdapterSave:
    """Tests for save method."""

    @pytest.mark.asyncio
    async def test_save_returns_checkpoint_id(self):
        repo = MockCheckpointRepository()
        adapter = CheckpointPersistenceAdapter(repo)
        state = {"step": 1, "data": "test"}

        checkpoint_id = await adapter.save("exec-1", state)

        assert checkpoint_id.startswith("cp-")
        assert len(checkpoint_id) == 15  # cp- + 12 hex chars

    @pytest.mark.asyncio
    async def test_save_persists_to_repo(self):
        repo = MockCheckpointRepository()
        adapter = CheckpointPersistenceAdapter(repo)
        state = {"key": "value"}

        checkpoint_id = await adapter.save("exec-1", state)

        checkpoint = await repo.get(checkpoint_id)
        assert checkpoint is not None
        assert checkpoint.execution_id == "exec-1"
        assert checkpoint.version == 1

    @pytest.mark.asyncio
    async def test_save_computes_hash(self):
        repo = MockCheckpointRepository()
        adapter = CheckpointPersistenceAdapter(repo)
        state = {"data": 123}

        checkpoint_id = await adapter.save("exec-1", state)

        checkpoint = await repo.get(checkpoint_id)
        assert checkpoint.checkpoint_hash is not None
        assert len(checkpoint.checkpoint_hash) == 16

    @pytest.mark.asyncio
    async def test_save_increments_version(self):
        repo = MockCheckpointRepository()
        adapter = CheckpointPersistenceAdapter(repo)

        id1 = await adapter.save("exec-1", {"v": 1})
        id2 = await adapter.save("exec-1", {"v": 2})

        cp1 = await repo.get(id1)
        cp2 = await repo.get(id2)
        assert cp2.version == cp1.version + 1

    @pytest.mark.asyncio
    async def test_save_sets_created_at(self):
        repo = MockCheckpointRepository()
        adapter = CheckpointPersistenceAdapter(repo)

        checkpoint_id = await adapter.save("exec-1", {"test": True})

        checkpoint = await repo.get(checkpoint_id)
        assert checkpoint.created_at is not None

    @pytest.mark.asyncio
    async def test_save_sets_agent_state_ref(self):
        repo = MockCheckpointRepository()
        adapter = CheckpointPersistenceAdapter(repo)
        state = {"test": True, "nested": {"key": "value"}}

        checkpoint_id = await adapter.save("exec-1", state)

        checkpoint = await repo.get(checkpoint_id)
        assert checkpoint.agent_state_ref is not None
        # agent_state_ref contains JSON of the state
        import json
        parsed = json.loads(checkpoint.agent_state_ref)
        assert parsed == state


class TestCheckpointPersistenceAdapterRestore:
    """Tests for restore method."""

    @pytest.mark.asyncio
    async def test_restore_returns_same_state(self):
        repo = MockCheckpointRepository()
        adapter = CheckpointPersistenceAdapter(repo)
        original_state = {"step": 3, "data": [1, 2, 3]}

        checkpoint_id = await adapter.save("exec-1", original_state)
        restored_state = await adapter.restore(checkpoint_id)

        assert restored_state == original_state

    @pytest.mark.asyncio
    async def test_restore_not_found_raises(self):
        repo = MockCheckpointRepository()
        adapter = CheckpointPersistenceAdapter(repo)

        with pytest.raises(CheckpointPersistenceError, match="not found"):
            await adapter.restore("cp-nonexistent")

    @pytest.mark.asyncio
    async def test_restore_preserves_complex_state(self):
        repo = MockCheckpointRepository()
        adapter = CheckpointPersistenceAdapter(repo)
        complex_state = {
            "nested": {"a": 1, "b": [2, 3]},
            "string": "hello",
            "number": 42,
            "boolean": True,
            "null": None,
        }

        checkpoint_id = await adapter.save("exec-1", complex_state)
        restored = await adapter.restore(checkpoint_id)

        assert restored == complex_state


class TestCheckpointPersistenceAdapterRoundtrip:
    """Tests for save/restore roundtrip metadata survival."""

    @pytest.mark.asyncio
    async def test_checkpoint_metadata_survives_roundtrip(self):
        repo = MockCheckpointRepository()
        adapter = CheckpointPersistenceAdapter(repo)

        checkpoint_id = await adapter.save("exec-1", {"test": True})

        # Verify checkpoint metadata via repo
        checkpoint = await repo.get(checkpoint_id)
        assert checkpoint.checkpoint_id == checkpoint_id
        assert checkpoint.execution_id == "exec-1"
        assert checkpoint.version == 1
        assert checkpoint.trigger_reason == CheckpointTrigger.STEP_COMPLETE
        assert checkpoint.checkpoint_hash is not None
        assert checkpoint.schema_version == "1.0"
        assert checkpoint.created_at is not None

    @pytest.mark.asyncio
    async def test_multiple_saves_different_execution_ids(self):
        repo = MockCheckpointRepository()
        adapter = CheckpointPersistenceAdapter(repo)

        id1 = await adapter.save("exec-1", {"exec": 1})
        id2 = await adapter.save("exec-2", {"exec": 2})

        assert id1 != id2
        state1 = await adapter.restore(id1)
        state2 = await adapter.restore(id2)
        assert state1 != state2

    @pytest.mark.asyncio
    async def test_restore_from_another_adapter(self):
        repo = MockCheckpointRepository()
        adapter1 = CheckpointPersistenceAdapter(repo)

        id1 = await adapter1.save("exec-1", {"shared": True})

        # Second adapter can restore because state is embedded in checkpoint
        adapter2 = CheckpointPersistenceAdapter(repo)
        state = await adapter2.restore(id1)
        assert state == {"shared": True}

    @pytest.mark.asyncio
    async def test_restore_no_state_in_checkpoint(self):
        repo = MockCheckpointRepository()
        adapter = CheckpointPersistenceAdapter(repo)

        # Create checkpoint without embedded state
        from core.domain.checkpoint import CheckpointTrigger
        cp = Checkpoint(
            checkpoint_id="cp-empty",
            execution_id="exec-1",
            version=1,
            trigger_reason=CheckpointTrigger.STEP_COMPLETE,
            checkpoint_hash="abc123",
            agent_state_ref=None,
        )
        await repo.save(cp)

        with pytest.raises(CheckpointPersistenceError, match="no state"):
            await adapter.restore("cp-empty")
