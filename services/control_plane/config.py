"""Control plane configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from services.control_plane.policy.types import PolicyConfig


@dataclass(frozen=True)
class ControlPlaneConfig:
    """Immutable configuration for control plane services."""
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    # Future configs can be added here