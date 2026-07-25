"""Capability domain model — typed capability with risk and permissions.

Every plugin declares its capabilities as typed objects, not raw strings.
The policy engine evaluates these before registration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class Capability:
    name: str
    risk_level: Literal["low", "medium", "high", "critical"]
    description: str = ""
    permissions: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if isinstance(self.permissions, list):
            object.__setattr__(self, "permissions", tuple(self.permissions))
