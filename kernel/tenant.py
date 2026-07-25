"""Tenant model — ownership and isolation contracts.

Defines TenantModel and TenantContext for enforcing tenant boundaries.
Every execution MUST have a valid TenantContext.
TenantContext is immutable during execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ResourceLimits:
    """Resource limits for a tenant."""

    max_agents: int = 10
    max_steps_per_agent: int = 10
    max_tokens_per_agent: int = 100_000
    max_concurrent_executions: int = 5
    max_checkpoints: int = 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_agents": self.max_agents,
            "max_steps_per_agent": self.max_steps_per_agent,
            "max_tokens_per_agent": self.max_tokens_per_agent,
            "max_concurrent_executions": self.max_concurrent_executions,
            "max_checkpoints": self.max_checkpoints,
        }


@dataclass(frozen=True)
class TenantModel:
    """A tenant in the Kitematic system.

    Tenant is the unit of ownership and resource allocation.
    Every Agent belongs to exactly one Tenant.
    Tenants cannot access each other's resources.
    """

    tenant_id: str
    name: str
    policy_scope: str = "default"
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)
    allowed_capabilities: frozenset[str] = frozenset()
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        """Validate tenant model integrity."""
        errors: list[str] = []
        if not self.tenant_id:
            errors.append("tenant_id is required")
        if not self.name:
            errors.append("name is required")
        return errors

    @property
    def is_valid(self) -> bool:
        return len(self.validate()) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "policy_scope": self.policy_scope,
            "resource_limits": self.resource_limits.to_dict(),
            "allowed_capabilities": sorted(self.allowed_capabilities),
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class TenantContext:
    """Immutable tenant context for a single execution.

    Captured at execution start and frozen until completion.
    Execution tenant_id CANNOT change mid-flight.

    Contains:
      - tenant_id: owning tenant
      - agent_id: executing agent
      - allowed_capabilities: tenant-scoped capabilities
      - resource_limits: tenant-scoped limits
    """

    tenant_id: str
    agent_id: str
    allowed_capabilities: frozenset[str] = frozenset()
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)

    def validate(self) -> list[str]:
        """Validate tenant context integrity."""
        errors: list[str] = []
        if not self.tenant_id:
            errors.append("tenant_id is required")
        if not self.agent_id:
            errors.append("agent_id is required")
        return errors

    @property
    def is_valid(self) -> bool:
        return len(self.validate()) == 0

    def has_capability(self, capability: str) -> bool:
        """Check if this context allows a specific capability."""
        if not self.allowed_capabilities:
            return True  # No restriction = allow all
        return capability in self.allowed_capabilities

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "agent_id": self.agent_id,
            "allowed_capabilities": sorted(self.allowed_capabilities),
            "resource_limits": self.resource_limits.to_dict(),
        }
