"""Marketplace invariants — rules that must always hold in the marketplace."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketplaceInvariants:
    """Invariants that must always hold in the marketplace."""

    # Maximum number of capabilities an extension can declare
    max_capabilities_per_extension: int = 50

    # Maximum length of capability IDs
    max_capability_id_length: int = 64

    # Required fields for extension manifest
    required_manifest_fields: tuple[str, ...] = (
        "extension_id",
        "name",
        "version",
        "extension_type",
        "publisher_id",
    )

    # Allowed extension types
    allowed_extension_types: tuple[str, ...] = (
        "agent",
        "tool",
        "model",
        "mcp",
    )

    # Maximum file size for extension artifacts (bytes)
    max_artifact_size: int = 100 * 1024 * 1024  # 100 MB

    # Allowed license identifiers (SPDX)
    allowed_licenses: tuple[str, ...] = (
        "MIT",
        "Apache-2.0",
        "BSD-3-Clause",
        "GPL-3.0",
        "LGPL-3.0",
        "MPL-2.0",
    )

    # Minimum runtime version compatibility
    min_runtime_version: str = "1.0"


# Singleton instance of marketplace invariants
MARKETPLACE_INVARIANTS = MarketplaceInvariants()
