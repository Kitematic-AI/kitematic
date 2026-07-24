"""Marketplace listing status and model."""

from __future__ import annotations

from enum import StrEnum


class ExtensionListingStatus(StrEnum):
    """Lifecycle status of an extension listing in the marketplace."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    DEPRECATED = "DEPRECATED"
    REMOVED = "REMOVED"

    # Valid transitions
    TRANSITIONS = {
        DRAFT: {SUBMITTED, REMOVED},
        SUBMITTED: {UNDER_REVIEW, REMOVED},
        UNDER_REVIEW: {APPROVED, DRAFT, REMOVED},
        APPROVED: {PUBLISHED, DEPRECATED, REMOVED},
        PUBLISHED: {DEPRECATED, REMOVED},
        DEPRECATED: {REMOVED},
        REMOVED: set(),
    }

    def can_transition(self, new_status) -> bool:
        """Check if transition to new_status is valid."""
        return new_status in self.TRANSITIONS.get(self, set())
