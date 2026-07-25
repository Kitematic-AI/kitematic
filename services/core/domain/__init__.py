"""Core domain models — shared kernel contracts."""

from __future__ import annotations

from core.policies.capability import (
    Capability,
    CapabilityCategory,
)
from core.policies.capability_catalog import CapabilityCatalog
from core.policies.capability_registry import CapabilityRegistry

__all__ = [
    "Capability",
    "CapabilityCategory",
    "CapabilityCatalog",
    "CapabilityRegistry",
]
