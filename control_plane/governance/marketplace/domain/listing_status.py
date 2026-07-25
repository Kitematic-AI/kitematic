"""Extension listing status enumeration."""

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
