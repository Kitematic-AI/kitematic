"""Checkpoint repository interface — snapshot storage contract."""

from abc import ABC, abstractmethod

from core.domain.checkpoint import Checkpoint


class CheckpointRepository(ABC):
    """Interface for checkpoint (snapshot) persistence.

    Each checkpoint is an immutable snapshot of execution state
    at a point in time. The repository guarantees:
    - save() stores a deep copy (caller mutation is safe)
    - get() returns a deep copy (internal state is protected)
    - get_latest() uses max(version), not insertion order
    """

    @abstractmethod
    async def save(self, checkpoint: Checkpoint) -> Checkpoint:
        """Persist a checkpoint snapshot. Returns the stored copy."""
        ...

    @abstractmethod
    async def get(self, checkpoint_id: str) -> Checkpoint | None:
        """Retrieve a checkpoint by ID. Returns None if not found."""
        ...

    @abstractmethod
    async def list_by_execution(self, execution_id: str) -> list[Checkpoint]:
        """List all checkpoints for an execution, ordered by version ascending."""
        ...

    @abstractmethod
    async def get_latest(self, execution_id: str) -> Checkpoint | None:
        """Get the highest-version checkpoint for an execution. Returns None if none."""
        ...
