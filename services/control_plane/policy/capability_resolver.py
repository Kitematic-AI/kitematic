"""CapabilityResolver — stateless service for capability resolution and validation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilityValidationResult:
    """Result of capability validation check."""
    valid: bool
    missing: tuple[str, ...] = ()


class CapabilityResolver:
    """Stateless service for capability resolution and validation.

    Responsibilities:
    - Capability lookup and normalization
    - Validation of required capabilities against registry
    - Capability entity resolution
    - Registry abstraction (decouples consumers from registry implementation)
    """

    def __init__(self, registry) -> None:
        self._registry = registry

    def validate_required(self, required: frozenset[str]) -> CapabilityValidationResult:
        """Validate that all required capabilities are registered.

        Args:
            required: Set of capability IDs that must be registered.

        Returns:
            CapabilityValidationResult with validity and missing capability IDs.
        """
        missing = tuple(cid for cid in required if not self._registry.contains(cid))
        return CapabilityValidationResult(valid=len(missing) == 0, missing=missing)

    def resolve(self, ids: frozenset[str]) -> list:
        """Resolve capability IDs to capability entities.

        Args:
            ids: Set of capability IDs to resolve.

        Returns:
            List of Capability entities for valid IDs (missing IDs are skipped).
        """
        return [self._registry.get(cid) for cid in ids if self._registry.contains(cid)]

    def is_registered(self, cap_id: str) -> bool:
        """Check if a capability ID is registered."""
        return self._registry.contains(cap_id)
