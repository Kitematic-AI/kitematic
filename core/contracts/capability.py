"""Capability binding contract — SPI for permission checks.

The runtime checks permissions through this protocol without coupling
to the binding implementation.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class CapabilityBindingProtocol(Protocol):
    """Permission check interface used by the runtime executor."""

    def can_execute(self, permission: str) -> bool:
        ...

    def validate_permissions(self, requested: set[str]) -> list[str]:
        ...
