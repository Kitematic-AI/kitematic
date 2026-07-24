"""Review service for extension submissions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class ReviewStatus(StrEnum):
    """Status of a review process."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"


class ReviewDecision(StrEnum):
    """Decision made by a reviewer."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REQUEST_CHANGES = "REQUEST_CHANGES"


@dataclass(frozen=True)
class ReviewDecisionRecord:
    """Record of a review decision."""

    decision: str
    reviewer_id: str
    reason: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: dict = None


class ReviewService:
    """Service for managing extension review processes."""

    def __init__(self):
        self._reviews: dict[str, dict] = {}

    async def submit_for_review(self, listing_id: str, submitter_id: str) -> str:
        """Submit a listing for review."""
        review_id = f"rev-{listing_id}"
        self._reviews[listing_id] = {
            "review_id": f"rev-{listing_id}",
            "listing_id": listing_id,
            "status": "PENDING",
            "submitted_by": submitter_id,
            "submitted_at": datetime.utcnow().isoformat(),
            "decisions": [],
        }
        return self._reviews[listing_id]["review_id"]

    async def record_decision(
        self,
        listing_id: str,
        decision: str,
        reviewer_id: str,
        reason: str,
    ) -> bool:
        """Record a review decision."""
        if listing_id not in self._reviews:
            return False
        self._reviews[listing_id]["decisions"].append({
            "decision": decision,
            "reviewer_id": reviewer_id,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
        })
        return True

    async def get_review(self, listing_id: str) -> dict | None:
        return self._reviews.get(listing_id)

    async def get_status(self, listing_id: str) -> str | None:
        review = self._reviews.get(listing_id)
        return review.get("status") if review else None
