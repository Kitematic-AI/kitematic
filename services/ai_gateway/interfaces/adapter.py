"""AI Gateway interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol

from runtime.domain.runtime_event import StreamChunk


# Type aliases for capability IDs (string IDs only, no Enum)
CapabilityId = str
CapabilitySet = tuple[str, ...]


@dataclass(frozen=True)
class AdapterHealth:
    """Health status of an adapter."""

    healthy: bool
    provider: str
    model: str = ""
    details: dict[str, Any] = field(default_factory=dict)


# Type aliases for capability IDs (string IDs only, no Enum)
CapabilityId = str
CapabilitySet = tuple[str, ...]


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
        """Check if adapter supports all required capabilities."""
        ...

    async def shutdown(self) -> None:
        """Graceful shutdown of the adapter."""
        ...


# Type aliases for capability IDs (string IDs only, no Enum)
CapabilityId = str
CapabilitySet = tuple[str, ...]


@dataclass(frozen=True)
class AdapterHealth:
    """Health status of an adapter."""

    healthy: bool
    provider: str
    model: str = ""
    details: dict[str, Any] = field(default_factory=dict)


# Type aliases for gateway
GatewayRequest = dict[str, Any]
GatewayResponse = dict[str, Any]