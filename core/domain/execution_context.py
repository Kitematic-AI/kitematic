"""Execution context — environment and authority for a single plugin execution.

Each call to a plugin's execute() is wrapped in an ExecutionContext that
carries the plugin identity, granted permissions, timeouts, and resource
limits. The executor uses this to enforce boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.domain.capability_binding import CapabilityBinding


@dataclass
class ExecutionContext:
    """Environment and authority for a single plugin execution.

    Attributes:
        plugin_name: Name of the plugin being executed.
        bindings: Capability bindings that grant permissions.
        timeout_seconds: Maximum wall-clock time for execution (0 = no limit).
        max_tokens: Maximum tokens the plugin may consume (0 = no limit).
        metadata: Arbitrary context passed by the caller.
    """

    plugin_name: str
    bindings: list[CapabilityBinding] = field(default_factory=list)
    timeout_seconds: float = 0.0
    max_tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def has_permission(self, permission: str) -> bool:
        """Check if any binding grants the requested permission.

        Args:
            permission: Permission string to check.

        Returns:
            True if at least one enabled binding allows this permission.
        """
        for binding in self.bindings:
            if binding.enabled and binding.can_execute(permission):
                return True
        return False

    def denied_permissions(self, requested: set[str]) -> list[str]:
        """Return requested permissions that no binding allows.

        Args:
            requested: Set of permission strings to validate.

        Returns:
            List of denied permission strings (empty = all allowed).
        """
        denied: list[str] = []
        for perm in requested:
            if not self.has_permission(perm):
                denied.append(perm)
        return denied
