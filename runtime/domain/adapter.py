"""Adapter domain model — Adapter Registry definitions and capabilities.

This module contains:
- The legacy Adapter dataclass (for backward compatibility)
- The new RuntimeAdapter Protocol (for runtime boundary contracts)
- AdapterType and TrustLevel enums (for adapter classification)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Protocol


class AdapterType(Enum):
    FRAMEWORK = "FRAMEWORK"
    MODEL = "MODEL"
    TOOL = "TOOL"
    MCP = "MCP"
    MEMORY = "MEMORY"
    EXECUTOR = "EXECUTOR"


class TrustLevel(Enum):
    T0_UNKNOWN = "T0_UNKNOWN"
    T1_COMMUNITY = "T1_COMMUNITY"
    T2_TESTED = "T2_TESTED"
    T3_ENTERPRISE = "T3_ENTERPRISE"
    T4_CRITICAL = "T4_CRITICAL"


@dataclass(frozen=True)
class Adapter:
    """A registered adapter in the Kitematic ecosystem."""

    adapter_id: str
    name: str
    type: AdapterType
    provider: str
    version: str
    trust_level: TrustLevel
    capabilities: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    status: str = "active"  # active, deprecated, retired
    created_at: datetime | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.adapter_id:
            errors.append("adapter_id is required")
        if not self.name:
            errors.append("name is required")
        return errors

    @property
    def is_valid(self) -> bool:
        return len(self.validate()) == 0

    @property
    def is_trusted(self) -> bool:
        return self.trust_level.value >= TrustLevel.T2_TESTED.value


# ── Protocol Contracts ──────────────────────────────────────────────────────


class RuntimeAdapter(Protocol):
    """Protocol for any executable adapter in the Kitematic runtime.

    This is a structural protocol — any class implementing these methods
    is a valid RuntimeAdapter. No base class inheritance required.
    Services implementing this protocol are runtime-compatible.
    """

    @property
    def adapter_id(self) -> str:
        """Unique identifier for this adapter."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name of the adapter."""
        ...

    @property
    def version(self) -> str:
        """Adapter version."""
        ...

    @property
    def capabilities(self) -> tuple[str, ...]:
        """Capabilities this adapter provides (as tuple of capability IDs)."""
        ...

    async def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        """Execute a single request synchronously."""
        ...

    async def execute_stream(self, request: dict[str, Any]) -> AsyncIterator[dict]:
        """Execute a request with streaming response."""
        ...

    async def health_check(self) -> dict[str, Any]:
        """Check adapter health status. Returns {'healthy': bool, ...}."""
        ...

    def supports(self, required_capabilities: frozenset[str]) -> bool:
        """Check if this adapter supports all required capabilities."""
        ...

    async def shutdown(self) -> None:
        """Graceful shutdown of the adapter."""
        ...


# Type aliases for capability IDs (protocol-native, no Enum dependency)
type CapabilityId = str
type CapabilitySet = frozenset[str]