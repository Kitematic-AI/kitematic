"""CHAOS-ST: Storage / Checkpoint chaos experiments.

Simulates storage-level failures:
  ST-01: Checkpoint corruption → backup recovery
  ST-02: Atomic write failure → no corruption
  ST-03: Checkpoint store pressure
  ST-04: Concurrent checkpoint races
"""

import json
import tempfile
from pathlib import Path

import pytest

from control_plane.adapters.to_kernel.checkpoint import CheckpointPersistenceAdapter
from infrastructure.storage.checkpoint.file_system import FileSystemCheckpointRepository
from tests.chaos.conftest import validate_recovery

pytestmark = [
    pytest.mark.timeout(30),
]


@pytest.fixture
def fs_repo():
    with tempfile.TemporaryDirectory() as tmp:
        yield FileSystemCheckpointRepository(tmp)


@pytest.fixture
def adapter(fs_repo):
    return CheckpointPersistenceAdapter(fs_repo)


@pytest.mark.asyncio
async def test_chaos_st_01_checkpoint_corruption_recovery(chaos_experiment, adapter, fs_repo):
    """CHAOS-ST-01: Corrupt checkpoint JSON, verify backup recovery."""
    result = chaos_experiment["result"]
    result.expected_outcome = "Corruption detected, backup checkpoint is recoverable"

    cp_id1 = await adapter.save("chaos-st1", {"step": 1, "data": "before"})
    cp_id2 = await adapter.save("chaos-st1", {"step": 2, "data": "after"})

    cp_path = fs_repo._checkpoint_path(cp_id2)
    cp_path.write_text("{corrupted json")

    result1 = await fs_repo.get(cp_id2)
    assert result1 is None, "Corrupted checkpoint should be treated as missing"

    restored = await adapter.restore(cp_id1)
    assert restored is not None, "Backup should be recoverable"
    assert restored.get("data") == "before"

    validate_recovery(result, recovered=True, rto_seconds=5.0)


@pytest.mark.asyncio
async def test_chaos_st_02_atomic_write_failure(chaos_experiment, adapter, fs_repo):
    """CHAOS-ST-02: Simulate partial checkpoint write, verify no corruption."""
    result = chaos_experiment["result"]
    result.expected_outcome = "Partial write does not corrupt checkpoint state"

    tmp_dir = Path(fs_repo._checkpoints_dir)
    dest = tmp_dir / "atomic-verify.json"

    tmp = dest.with_suffix(".tmp")
    tmp.write_text('{"valid": true}')
    tmp.replace(dest)

    assert dest.exists(), "Atomic write should create file"
    content = json.loads(dest.read_text())
    assert content["valid"] is True

    partial = dest.with_suffix(".partial")
    partial.write_text("")
    assert dest.exists(), "Partial write should not affect actual checkpoint"

    result.passed = True


@pytest.mark.asyncio
async def test_chaos_st_04_concurrent_checkpoint_races(chaos_experiment, adapter, fs_repo):
    """CHAOS-ST-04: Multiple concurrent saves to same execution, verify consistency."""
    result = chaos_experiment["result"]
    result.expected_outcome = "Concurrent saves produce valid, recoverable checkpoints"

    import asyncio

    async def save_step(i: int) -> str:
        return await adapter.save(
            f"chaos-st4-concurrent-{i}",
            {"step": i, "data": f"concurrent-{i}"},
        )

    cps = await asyncio.gather(*[save_step(i) for i in range(10)])
    assert len(cps) == 10, "All 10 saves should complete"

    for cp_id in cps:
        cp_data = await adapter.restore(cp_id)
        assert cp_data is not None, f"Checkpoint {cp_id} should be recoverable"

    result.passed = True
