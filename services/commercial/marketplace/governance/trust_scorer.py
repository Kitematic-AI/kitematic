"""Trust scoring for publishers and extensions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class TrustScore:
    """Trust score assessment result."""

    score: float  # 0.0 to 1.0
    tier: str  # "TRUSTED", "VERIFIED", "UNVERIFIED", "SUSPICIOUS"
    factors: dict = field(default_factory=dict)
    calculated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class TrustScorer:
    """Calculates trust scores for publishers and extensions."""

    def __init__(self):
        self._weights = {
            "publisher_verification": 0.3,
            "extension_age": 0.2,
            "download_count": 0.2,
            "review_score": 0.15,
            "security_scan": 0.15,
        }

    async def score_publisher(self, publisher) -> float:
        """Calculate trust score for a publisher."""
        score = 0.0
        if hasattr(publisher, "status") and publisher.status.value == "VERIFIED":
            score += self._weights["publisher_verification"]
        # Additional factors would be added here
        return min(1.0, score)

    async def score_extension(self, listing) -> float:
        """Calculate trust score for an extension listing."""
        score = 0.0
        # Placeholder scoring logic
        return min(1.0, score)

    async def get_trust_score(self, entity_id: str, entity_type: str) -> float:
        """Get trust score for an entity."""
        return 0.5  # placeholder