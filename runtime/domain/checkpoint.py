"""Checkpoint domain model — snapshots of execution state for time travel."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class CheckpointTrigger(Enum):
    STEP_COMPLETE = "STEP_COMPLETE"
    BEFORE_TOOL_CALL = "BEFORE_TOOL_CALL"
    AFTER_TOOL_CALL = "AFTER_TOOL_CALL"
    ERROR_RECOVERY = "ERROR_RECOVERY"
    PAUSE_REQUEST = "PAUSE_REQUEST"
    BEFORE_IRREVERSIBLE = "BEFORE_IRREVERSIBLE"


@dataclass(frozen=True)
class Checkpoint:
    """A point-in-time snapshot of execution state."""

    checkpoint_id: str
    execution_id: str
    version: int
    trigger_reason: CheckpointTrigger
    checkpoint_hash: str
    schema_version: str = "1.0"
    parent_checkpoint_id: str | None = None
    agent_state_ref: str | None = None  # key in object storage
    memory_refs: tuple[str, ...] = ()
    tool_history: tuple[dict[str, Any], ...] = ()
    created_at: datetime | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.checkpoint_id:
            errors.append("checkpoint_id is required")
        if not self.execution_id:
            errors.append("execution_id is required")
        if not self.checkpoint_hash:
            errors.append("checkpoint_hash is required")
        if self.version < 0:
            errors.append("version must be >= 0")
        return errors

    @property
    def is_valid(self) -> bool:
        return len(self.validate()) == 0
