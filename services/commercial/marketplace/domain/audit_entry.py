"""Marketplace audit entry domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class AuditAction(StrEnum):
    """Types of actions that can be audited."""

    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    PUBLISHED = "PUBLISHED"
    DEPRECATED = "DEPRECATED"
    REMOVED = "REMOVED"
    VERSION_ADDED = "VERSION_ADDED"
    VERSION_REMOVED = "VERSION_REMOVED"
    STATUS_CHANGED = "STATUS_CHANGED"
    METADATA_UPDATED = "METADATA_UPDATED"


@dataclass(frozen=True)
class AuditEntry:
    """Immutable audit log entry for marketplace activities."""

    entry_id: str
    listing_id: str
    action: "AuditAction"
    actor_id: str
    actor_role: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    changes: dict = None
    metadata: dict = None