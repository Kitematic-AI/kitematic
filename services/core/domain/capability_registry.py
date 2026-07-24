"""Capability Registry — runtime registry for capability definitions.

This module provides the CapabilityRegistry class which manages active capability
availability at runtime. It is separate from the CapabilityCatalog which provides
built-in capability definitions.

The registry:
- Manages active capability availability at runtime
- Validates capabilities on registration
- Provides O(1) lookup by capability ID
- Supports capability discovery and version resolution
"""

from __future__ import annotations

from services.core.domain.capability import Capability, CapabilityCategory


class CapabilityRegistry:
    """
    Runtime registry for capability definitions.

    Catalog provides built-in definitions.
    Registry manages active capability availability.

    Thread-safe for single-threaded use; not thread-safe for concurrent writes.
    """

    def __init__(
        self,
        capabilities: tuple = (),
    ) -> None:
        self._capabilities: dict[str, Capability] = {}

        for capability in capabilities:
            self.register(capability)

    def register(
        self,
        capability,
    ) -> None:
        """Register a capability after validation.

        Args:
            capability: The capability to register.

        Raises:
            ValueError: If the capability fails validation.
        """
        errors = capability.validate()

        if errors:
            raise ValueError(
                f"Invalid capability {capability.id}: {errors}"
            )

        self._capabilities[capability.id] = capability

    def get(
        self,
        capability_id: str,
    ) -> Capability | None:
        """Look up a capability by its ID."""
        return self._capabilities.get(capability_id)

    def contains(
        self,
        capability_id: str,
    ) -> bool:
        """Check if a capability is registered."""
        return capability_id in self._capabilities

    def list(
        self,
    ) -> tuple:
        """Return all registered capabilities as an immutable tuple."""
        return tuple(self._capabilities.values())

    def remove(
        self,
        capability_id: str,
    ) -> None:
        """Remove a capability from the registry."""
        self._capabilities.pop(
            capability_id,
            None,
        )

    def count(self) -> int:
        """Return the number of registered capabilities."""
        return len(self._capabilities)

    def query(
        self,
        category: CapabilityCategory | None = None,
        risk_level: str | None = None,
    ) -> tuple:
        """Query capabilities with optional filters.

        Args:
            category: Filter by capability category
            risk_level: Filter by risk level

        Returns:
            Tuple of matching capabilities
        """
        results = []
        for cap in self._capabilities.values():
            if category is not None and cap.category != category:
                continue
            if risk_level is not None and cap.risk_level != risk_level:
                continue
            results.append(cap)
        return tuple(results)

    def get_compatible(
        self,
        capability_id: str,
        version_constraint: str | None = None,
    ) -> tuple:
        """Get capabilities compatible with the given capability ID.

        Args:
            capability_id: The base capability ID to find compatibles for
            version_constraint: Optional version constraint (exact match in v1)

        Returns:
            Tuple of compatible capabilities
        """
        base_cap = self.get(capability_id)
        if not base_cap:
            return ()

        # v1: exact match only
        if version_constraint is None:
            return (self._capabilities[capability_id],)

        # Exact match only in v1
        compat = []
        for cap in self._capabilities.values():
            if cap.id == capability_id:
                compatible.append(cap)
        return tuple(compatible)

    def query(
        self,
        category: CapabilityCategory | None = None,
        risk_level: str | None = None,
    ) -> tuple:
        """Query capabilities with optional filters.

        Args:
            category: Filter by capability category
            risk_level: Filter by risk level

        Returns:
            Tuple of matching capabilities
        """
        results = []
        for cap in self._capabilities.values():
            if category is not None and cap.category != category:
                continue
            if risk_level is not None and cap.risk_level != risk_level:
                continue
            results.append(cap)
        return tuple(results)