"""Publisher domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class PublisherStatus(StrEnum):
    """Lifecycle status of a publisher in the marketplace."""

    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    VERIFIED = "VERIFIED"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"


@dataclass(frozen=True)
class Publisher:
    """Publisher identity in the marketplace."""

    publisher_id: str
    name: str
    email: str
    status: PublisherStatus = PublisherStatus.PENDING_VERIFICATION
    verified_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)

    def verify(self) -> Publisher:
        """Return a new verified publisher."""
        from datetime import datetime
        return Publisher(
            publisher_id=self.publisher_id,
            name=self.name,
            email=self.email,
            status=PublisherStatus.VERIFIED,
            verified_at=datetime.utcnow(),
            created_at=self.created_at,
            updated_at=datetime.utcnow(),
            metadata=self.metadata,
        )

    def suspend(self) -> Publisher:
        """Return a new suspended publisher."""
        from datetime import datetime
        return Publisher(
            publisher_id=self.publisher_id,
            name=self.name,
            email=self.email,
            status=PublisherStatus.SUSPENDED,
            verified_at=self.verified_at,
            created_at=self.created_at,
            updated_at=datetime.utcnow(),
            metadata=self.metadata,
        )
