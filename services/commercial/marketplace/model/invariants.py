"""Marketplace invariants and business rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MarketplaceInvariants:
    """
    Immutable invariants that must always hold in the marketplace.

    These are the fundamental business rules that must never be violated.
    """

    # Extension naming
    MIN_EXTENSION_ID_LENGTH: int = 3
    MAX_EXTENSION_ID_LENGTH: int = 64
    EXTENSION_ID_PATTERN: str = r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$|^[a-z0-9]$"

    # Versioning
    VERSION_PATTERN: str = r"^\d+\.\d+\.\d+(-[a-z0-9\.\-]+)?(\+[a-z0-9\.\-]+)?$"

    # Capability constraints
    MAX_CAPABILITIES_PER_EXTENSION: int = 50
    MIN_CAPABILITIES_PER_EXTENSION: int = 1

    # Versioning
    MAX_VERSIONS_PER_EXTENSION: int = 100
    MIN_VERSION_LENGTH: int = 5  # e.g., "1.0.0"

    # Publisher constraints
    MIN_PUBLISHER_NAME_LENGTH: int = 2
    MAX_PUBLISHER_NAME_LENGTH: int = 100
    MAX_PUBLISHERS_PER_ORG: int = 10

    # Versioning rules
    VERSION_COMPARISON_ORDER: tuple[str, ...] = (
        "major", "minor", "patch", "pre_release", "build"
    )

    # Extension metadata limits
    MAX_DESCRIPTION_LENGTH: int = 5000
    MAX_README_LENGTH: int = 100000
    MAX_TAGS_PER_EXTENSION: int = 20
    MAX_TAG_LENGTH: int = 32

    # Marketplace limits
    MAX_EXTENSIONS_PER_PUBLISHER: int = 500
    MAX_VERSIONS_PER_EXTENSION: int = 100

    # Review process
    MAX_REVIEW_TIME_DAYS: int = 14
    MIN_REVIEWERS_PER_EXTENSION: int = 1
    MAX_REVIEWERS_PER_EXTENSION: int = 3

    # Security
    MAX_FILE_SIZE_MB: int = 100
    ALLOWED_FILE_EXTENSIONS: tuple[str, ...] = (".py", ".json", ".yaml", ".yml", ".txt", ".md")

    @classmethod
    def validate_extension_id(cls, extension_id: str) -> list[str]:
        """Validate an extension ID against invariants."""
        import re
        errors = []

        if len(extension_id) < cls.MIN_EXTENSION_ID_LENGTH:
            errors.append(f"Extension ID too short (min {cls.MIN_EXTENSION_ID_LENGTH})")
        if len(extension_id) > cls.MAX_EXTENSION_ID_LENGTH:
            errors.append(f"Extension ID too long (max {cls.MAX_EXTENSION_ID_LENGTH})")

        pattern = cls.EXTENSION_ID_PATTERN
        if not re.match(pattern, extension_id):
            errors.append("Extension ID must be lowercase alphanumeric with hyphens")

        return errors

    @classmethod
    def validate_version(cls, version: str) -> list[str]:
        """Validate a version string."""
        import re
        errors = []

        if not re.match(cls.VERSION_PATTERN, version):
            errors.append(f"Invalid version format (expected semver): {version}")

        return errors

    @classmethod
    def validate_capabilities(cls, capabilities: list) -> list[str]:
        """Validate a list of capabilities."""
        errors = []

        if len(capabilities) > cls.MAX_CAPABILITIES_PER_EXTENSION:
            errors.append(f"Too many capabilities (max {cls.MAX_CAPABILITIES_PER_EXTENSION})")

        if len(capabilities) < cls.MIN_CAPABILITIES_PER_EXTENSION:
            errors.append(f"Too few capabilities (min {cls.MIN_CAPABILITIES_PER_EXTENSION})")

        return errors


# Singleton instance
MARKETPLACE_INVARIANTS = MarketplaceInvariants()