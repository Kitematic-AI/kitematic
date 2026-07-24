"""Capability domain model — unified capability identity and metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CapabilityCategory(str, Enum):
    """High-level capability categories for grouping and policy decisions."""

    MODEL = "model"
    TOOL = "tool"
    CODE = "code"
    MEDIA = "media"
    ENTERPRISE = "enterprise"
    SECURITY = "security"
    SYSTEM = "system"
    DEVICE = "device"
    FILESYSTEM = "filesystem"
    NETWORK = "network"


@dataclass(frozen=True)
class Capability:
    """Rich capability entity with full metadata.

    Unlike the legacy Enum, this entity supports rich metadata needed for
    marketplace, policy, pricing, and governance decisions.
    """

    id: str
    name: str
    category: CapabilityCategory
    risk_level: str = "low"  # low, medium, high, critical
    version: str = "1.0"
    description: str = ""
    requirements: dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        """Validate capability integrity."""
        errors = []
        if not self.id:
            errors.append("capability id required")
        if not self.name:
            errors.append("capability name required")
        return errors

    def __str__(self) -> str:
        return self.id
