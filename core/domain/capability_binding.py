"""Capability binding — links a plugin's capabilities to execution authority.

Each binding represents a granted capability for a specific plugin,
with the permissions that plugin is allowed to exercise.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CapabilityBinding:
    """Authorised capability grant for a plugin.

    Controls whether a plugin can execute a specific permission.
    """

    plugin_name: str
    capability_name: str
    permissions: tuple[str, ...] = field(default_factory=tuple)
    enabled: bool = True
    scope: str | None = None

    def can_execute(self, permission: str) -> bool:
        """Check if a specific permission is allowed by this binding.

        Args:
            permission: The permission string to check.

        Returns:
            True if the permission is in the allowed set and binding is enabled.
        """
        if not self.enabled:
            return False
        if permission in self.permissions:
            return True
        return permission in _expanded_permissions(self.permissions)

    def validate_permissions(self, requested: set[str]) -> list[str]:
        """Return requested permissions that are NOT allowed.

        Args:
            requested: Set of permission strings the plugin wants to use.

        Returns:
            List of denied permission strings (empty = all allowed).
        """
        if not self.enabled:
            return list(requested)
        denied: list[str] = []
        for perm in requested:
            if not self.can_execute(perm):
                denied.append(perm)
        return denied

    def disable(self) -> None:
        """Revoke this binding — no permissions will be granted."""
        self.enabled = False


def _expanded_permissions(permissions: tuple[str, ...]) -> set[str]:
    """Expand wildcard permissions into concrete entries.

    Currently supports trailing wildcard: "filesystem.*" → {"filesystem.read", ...}.
    For v1 this is a simple pass-through; expansion is stubbed for future use.
    """
    expanded: set[str] = set()
    for perm in permissions:
        if perm.endswith(".*"):
            expanded.add(perm)
        else:
            expanded.add(perm)
    return expanded
