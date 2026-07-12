"""In-memory CheckpointRepository implementation.

Stores checkpoints as deep-copied snapshots in a dict.
UUID-based IDs, version-based latest lookup.
"""

import copy
from uuid import uuid4

from runtime.domain.checkpoint import Checkpoint
from services.checkpoint.interfaces.checkpoint_repository import CheckpointRepository


class InMemoryCheckpointRepository(CheckpointRepository):
    """In-memory snapshot store with deep-copy immutability."""

    def __init__(self) -> None:
        self._store: dict[str, Checkpoint] = {}
        self._execution_index: dict[str, set[str]] = {}

    async def save(self, checkpoint: Checkpoint) -> Checkpoint:
        stored = copy.deepcopy(checkpoint)
        self._store[stored.checkpoint_id] = stored
        self._execution_index.setdefault(stored.execution_id, set()).add(
            stored.checkpoint_id
        )
        return copy.deepcopy(stored)

    async def get(self, checkpoint_id: str) -> Checkpoint | None:
        cp = self._store.get(checkpoint_id)
        return copy.deepcopy(cp) if cp is not None else None

    async def list_by_execution(self, execution_id: str) -> list[Checkpoint]:
        ids = self._execution_index.get(execution_id, set())
        checkpoints = [self._store[cid] for cid in ids]
        checkpoints.sort(key=lambda cp: (cp.version, cp.checkpoint_id))
        return [copy.deepcopy(cp) for cp in checkpoints]

    async def get_latest(self, execution_id: str) -> Checkpoint | None:
        ids = self._execution_index.get(execution_id, set())
        if not ids:
            return None
        best = max((self._store[cid] for cid in ids), key=lambda cp: cp.version)
        return copy.deepcopy(best)
