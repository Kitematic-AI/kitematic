"""Shared types for policy module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CapabilityValidationResult:
    """Result of capability validation check."""
    valid: bool
    missing: tuple[str, ...] = ()


class CapabilityResolver(Protocol):
    """Protocol for capability resolution and validation."""

    def validate_required(self, required: frozenset[str]) -> CapabilityValidationResult:
        """Validate that all required capabilities are registered."""
        ...

    def resolve(self, ids: frozenset[str]) -> list:
        """Resolve capability IDs to capability entities."""
        ...

    def is_registered(self, cap_id: str) -> bool:
        """Check if a capability ID is registered."""
        ...


class PolicyCache(Protocol):
    """Protocol for policy decision caching."""

    def get(self, key: str) -> dict | None:
        """Retrieve cached decision."""
        ...

    def set(self, key: str, value: dict) -> None:
        """Store decision in cache."""
        ...

    def invalidate(self, pattern: str | None = None) -> None:
        """Invalidate cache entries matching pattern."""
        ...


@dataclass(frozen=True)
class PolicyConfig:
    """Immutable configuration for policy engine."""
    cache_ttl_seconds: int = 300
    cache_max_entries: int = 10_000
    feature_flags: frozenset[str] = frozenset({
        "policy.cache",
        "policy.capability_validation",
        "observability.audit",
    })
