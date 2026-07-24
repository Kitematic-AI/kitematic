"""Core domain models — shared kernel contracts."""

from __future__ import annotations

from services.core.domain.capability import (
    Capability,
    CapabilityCategory,
)
from services.core.domain.capability_catalog import CapabilityCatalog
from services.core.domain.capability_registry import CapabilityRegistry

__all__ = [
    "Capability",
    "CapabilityCategory",
    "CapabilityCatalog",
    "CapabilityRegistry",
]
