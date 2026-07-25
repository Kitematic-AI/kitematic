"""Memory domain model — facts, preferences, and knowledge stored by Agents."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum


class MemoryType(Enum):
    FACT = "FACT"
    PREFERENCE = "PREFERENCE"
    SUMMARY = "SUMMARY"
    EXPERIENCE = "EXPERIENCE"
    DOCUMENT = "DOCUMENT"


@dataclass(frozen=True)
class MemoryItem:
    """A single item stored in Agent memory."""

    item_id: str
    tenant_id: str
    agent_instance_id: str
    type: MemoryType
    content: str
    confidence: float = 1.0
    source: str = ""
    created_at: datetime | None = None
    expires_at: datetime | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.item_id:
            errors.append("item_id is required")
        if not self.content:
            errors.append("content is required")
        if not (0.0 <= self.confidence <= 1.0):
            errors.append("confidence must be between 0.0 and 1.0")
        return errors

    @property
    def is_valid(self) -> bool:
        return len(self.validate()) == 0

    @property
    def is_expired(self) -> bool:
        if self.expires_at:
            return datetime.now(UTC) > self.expires_at
        return False
