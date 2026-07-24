"""Audit entry for marketplace operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class AuditAction(StrEnum):
    """Types of auditable actions."""

    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    PUBLISH = "PUBLISH"
    UNPUBLISH = "UNPUBLISH"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    DEPRECATE = "DEPRECATE"
    SUBMIT = "SUBMIT"
    WITHDRAW = "WITHDRAW"


@dataclass(frozen=True)
class AuditEntry:
    """Immutable audit log entry."""

    entry_id: str
    action: AuditAction
    actor_id: str
    resource_type: str  # "extension", "publisher", "policy"
    resource_id: str
    old_state: dict = None
    new_state: dict = None
    reason: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "entry_id": self.entry_id,
            "action": self.action.value,
            "actor_id": self.actor_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "old_state": self.old_state,
            "new_state": self.new_state,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }