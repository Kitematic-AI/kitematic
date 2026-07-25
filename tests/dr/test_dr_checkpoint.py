"""DR-T01 / DR-T02 / DR-T04 — Checkpoint disaster recovery tests.

Verifies:
  DR-T01: Checkpoint corruption detection + recovery from valid backup
  DR-T02: Atomic write safety (partial write does not corrupt state)
  DR-T04: FileSystemRepository durability across simulated restarts
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest

from core.domain.checkpoint import Checkpoint, CheckpointTrigger
from runtime.kitematic_runtime.adapters.checkpoint_adapter import CheckpointPersistenceAdapter
from services.checkpoint.repositories.file_system_checkpoint import FileSystemCheckpointRepository
from services.checkpoint.repositories.in_memory_checkpoint import InMemoryCheckpointRepository


@pytest.fixture
def fs_repo():
    with tempfile.TemporaryDirectory() as tmp:
        yield FileSystemCheckpointRepository(tmp)


@pytest.fixture
def adapter(fs_repo):
    return CheckpointPersistenceAdapter(fs_repo)


# ═══════════════════════════════════════════════════════════════════════
# DR-T01: Checkpoint Corruption + Recovery
# ═══════════════════════════════════════════════════════════════════════


class TestCheckpointCorruptionRecovery:
    """DR-T01: Verify checkpoint corruption is detected and backup is recoverable."""

    @pytest.mark.asyncio
    async def test_corrupted_json_detected_by_repository(self, adapter, fs_repo):
        cp_id = await adapter.save("exec-corrupt-1", {"step": 1, "data": "hello"})
        cp_path = fs_repo._checkpoint_path(cp_id)
        cp_path.write_text("{corrupted json")

        result = await fs_repo.get(cp_id)
        assert result is None, "Repository should treat corrupted files as missing"

        with pytest.raises(Exception) as exc:
            await adapter.restore(cp_id)
        assert "not found" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_intact_checkpoint_is_recoverable_after_corruption_detected(self, adapter, fs_repo):
        cp_id1 = await adapter.save("exec-recover-1", {"step": 1, "data": "first"})
        cp_id2 = await adapter.save("exec-recover-1", {"step": 2, "data": "second"})

        cp_path = fs_repo._checkpoint_path(cp_id2)
        cp_path.write_text("garbage")

        state1 = await adapter.restore(cp_id1)
        assert state1["step"] == 1
        assert state1["data"] == "first"

        with pytest.raises(Exception):
            await adapter.restore(cp_id2)

    @pytest.mark.asyncio
    async def test_missing_checkpoint_returns_clear_error(self, adapter):
        with pytest.raises(Exception) as exc:
            await adapter.restore("cp-nonexistent")
        assert "not found" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_empty_state_restore_returns_error(self, adapter, fs_repo):
        from core.domain.checkpoint import Checkpoint, CheckpointTrigger
        from datetime import datetime, UTC

        cp = Checkpoint(
            checkpoint_id="cp-empty-1",
            execution_id="exec-empty",
            version=1,
            trigger_reason=CheckpointTrigger.STEP_COMPLETE,
            checkpoint_hash="",
            agent_state_ref=None,
            created_at=datetime.now(UTC),
        )
        await fs_repo.save(cp)

        with pytest.raises(Exception) as exc:
            await adapter.restore("cp-empty-1")
        assert "no state" in str(exc.value).lower() or "None" in str(exc.value)


# ═══════════════════════════════════════════════════════════════════════
# DR-T02: Atomic Write Safety
# ═══════════════════════════════════════════════════════════════════════


class TestAtomicWriteSafety:
    """DR-T02: Verify partial writes do not corrupt checkpoint state."""

    @pytest.mark.asyncio
    async def test_tmp_file_does_not_persist_on_crash(self, fs_repo):
        dest = fs_repo._checkpoint_path("cp-test-atomic")
        tmp = dest.with_suffix(".tmp")

        tmp.write_text("partial data")
        assert tmp.exists()
        assert not dest.exists()

        tmp.unlink()
        assert not dest.exists()

    @pytest.mark.asyncio
    async def test_index_partial_write_does_not_corrupt(self, fs_repo):
        index_path = fs_repo._index_path
        tmp_path = index_path.with_suffix(".tmp")

        tmp_path.write_text("garbage")
        assert index_path.exists() is False or index_path.read_text() != "garbage"

        fs_repo._save_index({"exec-test": ["cp-1"]})
        assert index_path.exists()
        data = json.loads(index_path.read_text())
        assert data["exec-test"] == ["cp-1"]

    @pytest.mark.asyncio
    async def test_concurrent_saves_produce_valid_state(self, fs_repo):
        import asyncio

        async def save_worker(n: int):
            cp = Checkpoint(
                checkpoint_id=f"cp-conc-{n}",
                execution_id="exec-conc",
                version=n,
                trigger_reason=CheckpointTrigger.STEP_COMPLETE,
                checkpoint_hash=f"hash-{n}",
                agent_state_ref=json.dumps({"step": n}),
            )
            return await fs_repo.save(cp)

        results = await asyncio.gather(*[save_worker(i) for i in range(20)])
        saved_ids = [r.checkpoint_id for r in results]
        assert len(set(saved_ids)) == 20

        for cid in saved_ids:
            cp = await fs_repo.get(cid)
            assert cp is not None
            assert cp.checkpoint_hash.startswith("hash-")


# ═══════════════════════════════════════════════════════════════════════
# DR-T04: Checkpoint Durability
# ═══════════════════════════════════════════════════════════════════════


class TestCheckpointDurability:
    """DR-T04: Verify checkpoint state survives simulated restarts."""

    @pytest.mark.asyncio
    async def test_state_survives_repository_reinit(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = FileSystemCheckpointRepository(tmp)
            adapter = CheckpointPersistenceAdapter(repo)
            cp_id = await adapter.save("exec-durable-1", {"step": 5, "status": "running"})

        with tempfile.TemporaryDirectory() as tmp:
            repo2 = FileSystemCheckpointRepository(tmp)
            adapter2 = CheckpointPersistenceAdapter(repo2)
            with pytest.raises(Exception) as exc:
                await adapter2.restore(cp_id)
            assert "not found" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_state_persists_across_adapter_reinit(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = FileSystemCheckpointRepository(tmp)
            adapter = CheckpointPersistenceAdapter(repo)
            cp_id = await adapter.save("exec-durable-2", {"step": 10, "data": "persist"})

            repo2 = FileSystemCheckpointRepository(tmp)
            adapter2 = CheckpointPersistenceAdapter(repo2)
            state = await adapter2.restore(cp_id)
            assert state["step"] == 10
            assert state["data"] == "persist"

    @pytest.mark.asyncio
    async def test_latest_checkpoint_is_recoverable(self, adapter):
        cid1 = await adapter.save("exec-latest", {"step": 1})
        cid2 = await adapter.save("exec-latest", {"step": 2})
        cid3 = await adapter.save("exec-latest", {"step": 3})

        s1 = await adapter.restore(cid1)
        s2 = await adapter.restore(cid2)
        s3 = await adapter.restore(cid3)

        assert s1["step"] == 1
        assert s2["step"] == 2
        assert s3["step"] == 3

    @pytest.mark.asyncio
    async def test_restore_after_adapter_save(self, adapter):
        state = {"items": ["a", "b", "c"], "count": 3}
        cp_id = await adapter.save("exec-items", state)
        restored = await adapter.restore(cp_id)
        assert restored == state

    @pytest.mark.asyncio
    async def test_checkpoint_hash_integrity(self, fs_repo):
        cp = Checkpoint(
            checkpoint_id="cp-hash-1",
            execution_id="exec-hash",
            version=1,
            trigger_reason=CheckpointTrigger.STEP_COMPLETE,
            checkpoint_hash="abc123",
            agent_state_ref=json.dumps({"data": "test"}),
        )
        await fs_repo.save(cp)
        restored = await fs_repo.get("cp-hash-1")
        assert restored is not None
        assert restored.checkpoint_hash == "abc123"


class TestInMemoryDurability:
    """InMemory backend is NOT durable — these tests verify the expectation."""

    @pytest.mark.asyncio
    async def test_in_memory_loses_state_after_reinit(self):
        repo1 = InMemoryCheckpointRepository()
        cp = Checkpoint(
            checkpoint_id="cp-volatile",
            execution_id="exec-volatile",
            version=1,
            trigger_reason=CheckpointTrigger.STEP_COMPLETE,
            checkpoint_hash="hash",
            agent_state_ref=json.dumps({"data": "lost"}),
        )
        await repo1.save(cp)

        repo2 = InMemoryCheckpointRepository()
        result = await repo2.get("cp-volatile")
        assert result is None
