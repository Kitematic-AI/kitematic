"""Isolation boundary — enforces tenant and agent isolation.

Every state access and checkpoint operation MUST go through IsolationBoundary.
Cross-tenant access is always denied.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from runtime.kitematic_runtime.tenant import TenantContext, TenantModel


class IsolationError(Exception):
    """Base exception for isolation violations."""

    def __init__(self, message: str, tenant_id: str = "", agent_id: str = ""):
        self.tenant_id = tenant_id
        self.agent_id = agent_id
        super().__init__(message)


class TenantNotFoundError(IsolationError):
    """Raised when a tenant is not registered."""

    def __init__(self, tenant_id: str):
        super().__init__(f"Tenant not found: {tenant_id}", tenant_id=tenant_id)


class AgentNotInTenantError(IsolationError):
    """Raised when an agent is not registered with the expected tenant."""

    def __init__(self, agent_id: str, expected_tenant: str, actual_tenant: str):
        self.expected_tenant = expected_tenant
        self.actual_tenant = actual_tenant
        super().__init__(
            f"Agent '{agent_id}' not in tenant '{expected_tenant}' "
            f"(registered with '{actual_tenant}')",
            tenant_id=expected_tenant,
            agent_id=agent_id,
        )


class CrossTenantAccessError(IsolationError):
    """Raised when cross-tenant access is attempted."""

    def __init__(self, requesting_tenant: str, target_tenant: str, resource: str):
        self.target_tenant = target_tenant
        self.resource = resource
        super().__init__(
            f"Cross-tenant access denied: tenant '{requesting_tenant}' "
            f"cannot access '{resource}' in tenant '{target_tenant}'",
            tenant_id=requesting_tenant,
        )


class CrossAgentAccessError(IsolationError):
    """Raised when cross-agent access is attempted."""

    def __init__(self, requesting_agent: str, target_agent: str, resource: str):
        self.target_agent = target_agent
        self.resource = resource
        super().__init__(
            f"Cross-agent access denied: agent '{requesting_agent}' "
            f"cannot access '{resource}' owned by agent '{target_agent}'",
            agent_id=requesting_agent,
        )


class MissingTenantContextError(IsolationError):
    """Raised when execution is attempted without tenant context."""

    def __init__(self) -> None:
        super().__init__("No tenant context — execution denied")


class ResourceLimitExceededError(IsolationError):
    """Raised when tenant resource limits are exceeded."""

    def __init__(self, tenant_id: str, limit_type: str, current: int, max_val: int):
        self.limit_type = limit_type
        self.current = current
        self.max_val = max_val
        super().__init__(
            f"Resource limit exceeded for tenant '{tenant_id}': "
            f"{limit_type} = {current} > {max_val}",
            tenant_id=tenant_id,
        )


@dataclass
class AgentRecord:
    """Internal record of an agent's tenant membership."""

    agent_id: str
    tenant_id: str
    registered_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class IsolationBoundary:
    """Enforces tenant and agent isolation.

    Responsibilities:
      - Register tenants and agents
      - Validate agent→tenant membership
      - Validate state ownership
      - Validate checkpoint ownership
      - Enforce resource limits

    Does NOT:
      - Make policy decisions
      - Execute intents
      - Access tools
    """

    def __init__(self) -> None:
        self._tenants: dict[str, TenantModel] = {}
        self._agents: dict[str, AgentRecord] = {}
        self._execution_counts: dict[str, int] = {}  # tenant_id → active count

    # ── Registration ──────────────────────────────────────────────────

    def register_tenant(self, tenant: TenantModel) -> None:
        """Register a tenant."""
        if not tenant.is_valid:
            raise ValueError(f"Invalid tenant: {tenant.validate()}")
        self._tenants[tenant.tenant_id] = tenant

    def register_agent(self, agent_id: str, tenant_id: str) -> None:
        """Register an agent with a tenant."""
        if tenant_id not in self._tenants:
            raise TenantNotFoundError(tenant_id)
        self._agents[agent_id] = AgentRecord(agent_id=agent_id, tenant_id=tenant_id)

    def get_tenant(self, tenant_id: str) -> TenantModel | None:
        """Get a registered tenant."""
        return self._tenants.get(tenant_id)

    def get_agent_tenant(self, agent_id: str) -> str | None:
        """Get the tenant ID for an agent."""
        record = self._agents.get(agent_id)
        return record.tenant_id if record else None

    def list_tenants(self) -> list[str]:
        """List all registered tenant IDs."""
        return list(self._tenants.keys())

    def list_agents(self, tenant_id: str) -> list[str]:
        """List all agent IDs for a tenant."""
        return [a.agent_id for a in self._agents.values() if a.tenant_id == tenant_id]

    # ── Validation ────────────────────────────────────────────────────

    def validate_agent_scope(self, agent_id: str, tenant_id: str) -> bool:
        """Validate agent belongs to the specified tenant.

        Returns True if valid, raises if not.
        """
        record = self._agents.get(agent_id)
        if record is None:
            raise AgentNotInTenantError(agent_id, tenant_id, "unregistered")
        if record.tenant_id != tenant_id:
            raise AgentNotInTenantError(agent_id, tenant_id, record.tenant_id)
        return True

    def validate_tenant_context(self, context: TenantContext) -> bool:
        """Validate a tenant context is valid and registered.

        Returns True if valid, raises if not.
        """
        if not context.is_valid:
            raise MissingTenantContextError()
        tenant = self._tenants.get(context.tenant_id)
        if tenant is None:
            raise TenantNotFoundError(context.tenant_id)
        self.validate_agent_scope(context.agent_id, context.tenant_id)
        return True

    def validate_state_owner(
        self,
        state_tenant: str,
        state_agent: str,
        request_tenant: str,
        request_agent: str,
    ) -> bool:
        """Validate state ownership.

        Returns True if the request can access the state.
        Raises CrossTenantAccessError or CrossAgentAccessError if denied.
        """
        # Tenant boundary check
        if state_tenant != request_tenant:
            raise CrossTenantAccessError(
                requesting_tenant=request_tenant,
                target_tenant=state_tenant,
                resource=f"state:{state_agent}",
            )
        # Agent boundary check
        if state_agent != request_agent:
            raise CrossAgentAccessError(
                requesting_agent=request_agent,
                target_agent=state_agent,
                resource=f"state:{state_agent}",
            )
        return True

    def validate_checkpoint_owner(
        self,
        checkpoint_tenant: str,
        checkpoint_agent: str,
        request_tenant: str,
        request_agent: str,
    ) -> bool:
        """Validate checkpoint ownership.

        Returns True if the request can access the checkpoint.
        Raises CrossTenantAccessError or CrossAgentAccessError if denied.
        """
        # Tenant boundary check
        if checkpoint_tenant != request_tenant:
            raise CrossTenantAccessError(
                requesting_tenant=request_tenant,
                target_tenant=checkpoint_tenant,
                resource=f"checkpoint:{checkpoint_agent}",
            )
        # Agent boundary check
        if checkpoint_agent != request_agent:
            raise CrossAgentAccessError(
                requesting_agent=request_agent,
                target_agent=checkpoint_agent,
                resource=f"checkpoint:{checkpoint_agent}",
            )
        return True

    # ── Resource Limits ───────────────────────────────────────────────

    def check_resource_limits(self, tenant_id: str) -> None:
        """Check tenant resource limits before starting execution."""
        tenant = self._tenants.get(tenant_id)
        if tenant is None:
            raise TenantNotFoundError(tenant_id)

        current_count = self._execution_counts.get(tenant_id, 0)
        max_concurrent = tenant.resource_limits.max_concurrent_executions

        if current_count >= max_concurrent:
            raise ResourceLimitExceededError(
                tenant_id=tenant_id,
                limit_type="concurrent_executions",
                current=current_count,
                max_val=max_concurrent,
            )

    def start_execution(self, tenant_id: str) -> None:
        """Record execution start for resource tracking."""
        self._execution_counts[tenant_id] = self._execution_counts.get(tenant_id, 0) + 1

    def end_execution(self, tenant_id: str) -> None:
        """Record execution end for resource tracking."""
        current = self._execution_counts.get(tenant_id, 0)
        self._execution_counts[tenant_id] = max(0, current - 1)

    # ── Serialization ─────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize isolation boundary state."""
        return {
            "tenants": {tid: t.to_dict() for tid, t in self._tenants.items()},
            "agents": {
                aid: {"agent_id": r.agent_id, "tenant_id": r.tenant_id}
                for aid, r in self._agents.items()
            },
            "execution_counts": dict(self._execution_counts),
        }
