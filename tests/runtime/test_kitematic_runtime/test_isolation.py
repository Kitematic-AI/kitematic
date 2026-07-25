"""Tests for IsolationBoundary — tenant and agent isolation enforcement.

Verifies:
  - Tenant registration
  - Agent registration
  - Agent scope validation
  - State ownership validation
  - Checkpoint ownership validation
  - Cross-tenant access denial
  - Cross-agent access denial
  - Resource limit enforcement
  - Serialization
"""

import pytest

from kernel.isolation import (
    AgentNotInTenantError,
    CrossAgentAccessError,
    CrossTenantAccessError,
    IsolationBoundary,
    MissingTenantContextError,
    ResourceLimitExceededError,
    TenantNotFoundError,
)
from kernel.tenant import ResourceLimits, TenantContext, TenantModel

# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def boundary():
    return IsolationBoundary()


@pytest.fixture
def tenant_a():
    return TenantModel(tenant_id="t1", name="Tenant A")


@pytest.fixture
def tenant_b():
    return TenantModel(tenant_id="t2", name="Tenant B")


@pytest.fixture
def tenant_a_registered(boundary, tenant_a):
    boundary.register_tenant(tenant_a)
    return tenant_a


@pytest.fixture
def tenant_b_registered(boundary, tenant_b):
    boundary.register_tenant(tenant_b)
    return tenant_b


@pytest.fixture
def agent_a_registered(boundary, tenant_a_registered):
    boundary.register_agent("a1", "t1")
    return "a1"


@pytest.fixture
def agent_b_registered(boundary, tenant_b_registered):
    boundary.register_agent("a2", "t2")
    return "a2"


# ── Registration Tests ──────────────────────────────────────────────────


class TestRegistration:
    def test_register_tenant(self, boundary, tenant_a):
        boundary.register_tenant(tenant_a)
        assert boundary.get_tenant("t1") is tenant_a

    def test_register_invalid_tenant_raises(self, boundary):
        invalid = TenantModel(tenant_id="", name="")
        with pytest.raises(ValueError):
            boundary.register_tenant(invalid)

    def test_register_agent(self, boundary, tenant_a_registered):
        boundary.register_agent("a1", "t1")
        assert boundary.get_agent_tenant("a1") == "t1"

    def test_register_agent_tenant_not_found(self, boundary):
        with pytest.raises(TenantNotFoundError):
            boundary.register_agent("a1", "nonexistent")

    def test_list_tenants(self, boundary, tenant_a_registered, tenant_b_registered):
        tenants = boundary.list_tenants()
        assert "t1" in tenants
        assert "t2" in tenants

    def test_list_agents(self, boundary, tenant_a_registered):
        boundary.register_agent("a1", "t1")
        boundary.register_agent("a2", "t1")
        agents = boundary.list_agents("t1")
        assert "a1" in agents
        assert "a2" in agents


# ── Agent Scope Validation Tests ────────────────────────────────────────


class TestAgentScope:
    def test_validate_agent_scope_success(
        self, boundary, tenant_a_registered, agent_a_registered
    ):
        assert boundary.validate_agent_scope("a1", "t1") is True

    def test_validate_agent_scope_wrong_tenant(
        self, boundary, tenant_a_registered, agent_a_registered
    ):
        with pytest.raises(AgentNotInTenantError):
            boundary.validate_agent_scope("a1", "t2")

    def test_validate_agent_scope_unregistered(self, boundary):
        with pytest.raises(AgentNotInTenantError):
            boundary.validate_agent_scope("unknown", "t1")


# ── Tenant Context Validation Tests ─────────────────────────────────────


class TestTenantContextValidation:
    def test_validate_tenant_context_success(
        self, boundary, tenant_a_registered, agent_a_registered
    ):
        ctx = TenantContext(tenant_id="t1", agent_id="a1")
        assert boundary.validate_tenant_context(ctx) is True

    def test_validate_tenant_context_empty(self, boundary):
        ctx = TenantContext(tenant_id="", agent_id="")
        with pytest.raises(MissingTenantContextError):
            boundary.validate_tenant_context(ctx)

    def test_validate_tenant_context_tenant_not_found(self, boundary):
        ctx = TenantContext(tenant_id="nonexistent", agent_id="a1")
        with pytest.raises(TenantNotFoundError):
            boundary.validate_tenant_context(ctx)

    def test_validate_tenant_context_agent_wrong_tenant(
        self, boundary, tenant_a_registered, tenant_b_registered
    ):
        boundary.register_agent("a1", "t1")
        ctx = TenantContext(tenant_id="t2", agent_id="a1")
        with pytest.raises(AgentNotInTenantError):
            boundary.validate_tenant_context(ctx)


# ── State Ownership Tests ───────────────────────────────────────────────


class TestStateOwnership:
    def test_same_tenant_same_agent(self, boundary):
        assert boundary.validate_state_owner("t1", "a1", "t1", "a1") is True

    def test_same_tenant_different_agent(self, boundary):
        with pytest.raises(CrossAgentAccessError):
            boundary.validate_state_owner("t1", "a1", "t1", "a2")

    def test_different_tenant_same_agent(self, boundary):
        with pytest.raises(CrossTenantAccessError):
            boundary.validate_state_owner("t1", "a1", "t2", "a1")

    def test_different_tenant_different_agent(self, boundary):
        with pytest.raises(CrossTenantAccessError):
            boundary.validate_state_owner("t1", "a1", "t2", "a2")


# ── Checkpoint Ownership Tests ──────────────────────────────────────────


class TestCheckpointOwnership:
    def test_same_tenant_same_agent(self, boundary):
        assert boundary.validate_checkpoint_owner("t1", "a1", "t1", "a1") is True

    def test_same_tenant_different_agent(self, boundary):
        with pytest.raises(CrossAgentAccessError):
            boundary.validate_checkpoint_owner("t1", "a1", "t1", "a2")

    def test_different_tenant_same_agent(self, boundary):
        with pytest.raises(CrossTenantAccessError):
            boundary.validate_checkpoint_owner("t1", "a1", "t2", "a1")

    def test_different_tenant_different_agent(self, boundary):
        with pytest.raises(CrossTenantAccessError):
            boundary.validate_checkpoint_owner("t1", "a1", "t2", "a2")


# ── Resource Limit Tests ────────────────────────────────────────────────


class TestResourceLimits:
    def test_check_limits_within_bounds(self, boundary, tenant_a_registered):
        boundary.check_resource_limits("t1")  # should not raise

    def test_check_limits_tenant_not_found(self, boundary):
        with pytest.raises(TenantNotFoundError):
            boundary.check_resource_limits("nonexistent")

    def test_check_limits_exceeded(self, boundary):
        limits = ResourceLimits(max_concurrent_executions=1)
        tenant = TenantModel(tenant_id="t1", name="T", resource_limits=limits)
        boundary.register_tenant(tenant)
        boundary.start_execution("t1")
        with pytest.raises(ResourceLimitExceededError):
            boundary.check_resource_limits("t1")

    def test_start_end_execution_tracking(self, boundary, tenant_a_registered):
        boundary.start_execution("t1")
        boundary.start_execution("t1")
        assert boundary._execution_counts["t1"] == 2
        boundary.end_execution("t1")
        assert boundary._execution_counts["t1"] == 1
        boundary.end_execution("t1")
        assert boundary._execution_counts["t1"] == 0

    def test_end_execution_floor_zero(self, boundary, tenant_a_registered):
        boundary.end_execution("t1")
        assert boundary._execution_counts["t1"] == 0


# ── Serialization Tests ─────────────────────────────────────────────────


class TestSerialization:
    def test_to_dict(self, boundary, tenant_a_registered, agent_a_registered):
        d = boundary.to_dict()
        assert "tenants" in d
        assert "agents" in d
        assert "execution_counts" in d
        assert "t1" in d["tenants"]
        assert "a1" in d["agents"]
        assert d["agents"]["a1"]["tenant_id"] == "t1"
