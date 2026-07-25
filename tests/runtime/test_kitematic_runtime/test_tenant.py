"""Tests for Tenant model — ownership and isolation contracts.

Verifies:
  - TenantModel creation and validation
  - TenantContext immutability
  - ResourceLimits defaults
  - has_capability check
  - Serialization
"""

import pytest

from kernel.tenant import (
    ResourceLimits,
    TenantContext,
    TenantModel,
)

# ── TenantModel Tests ───────────────────────────────────────────────────


class TestTenantModel:
    def test_create_valid_tenant(self):
        tenant = TenantModel(tenant_id="t1", name="Test Tenant")
        assert tenant.tenant_id == "t1"
        assert tenant.name == "Test Tenant"
        assert tenant.policy_scope == "default"
        assert tenant.is_valid

    def test_tenant_with_custom_policy_scope(self):
        tenant = TenantModel(tenant_id="t1", name="T", policy_scope="restricted")
        assert tenant.policy_scope == "restricted"

    def test_tenant_with_resource_limits(self):
        limits = ResourceLimits(max_agents=5, max_steps_per_agent=20)
        tenant = TenantModel(tenant_id="t1", name="T", resource_limits=limits)
        assert tenant.resource_limits.max_agents == 5
        assert tenant.resource_limits.max_steps_per_agent == 20

    def test_tenant_with_capabilities(self):
        caps = frozenset(["read", "write", "execute"])
        tenant = TenantModel(tenant_id="t1", name="T", allowed_capabilities=caps)
        assert "read" in tenant.allowed_capabilities
        assert "write" in tenant.allowed_capabilities

    def test_tenant_invalid_empty_id(self):
        tenant = TenantModel(tenant_id="", name="T")
        assert not tenant.is_valid
        errors = tenant.validate()
        assert any("tenant_id" in e for e in errors)

    def test_tenant_invalid_empty_name(self):
        tenant = TenantModel(tenant_id="t1", name="")
        assert not tenant.is_valid
        errors = tenant.validate()
        assert any("name" in e for e in errors)

    def test_tenant_frozen(self):
        tenant = TenantModel(tenant_id="t1", name="T")
        with pytest.raises(AttributeError):
            tenant.tenant_id = "t2"

    def test_tenant_to_dict(self):
        tenant = TenantModel(
            tenant_id="t1",
            name="Test",
            allowed_capabilities=frozenset(["cap1"]),
        )
        d = tenant.to_dict()
        assert d["tenant_id"] == "t1"
        assert d["name"] == "Test"
        assert d["allowed_capabilities"] == ["cap1"]
        assert "resource_limits" in d

    def test_tenant_metadata(self):
        tenant = TenantModel(
            tenant_id="t1",
            name="T",
            metadata={"env": "production"},
        )
        assert tenant.metadata["env"] == "production"


# ── ResourceLimits Tests ────────────────────────────────────────────────


class TestResourceLimits:
    def test_default_limits(self):
        limits = ResourceLimits()
        assert limits.max_agents == 10
        assert limits.max_steps_per_agent == 10
        assert limits.max_tokens_per_agent == 100_000
        assert limits.max_concurrent_executions == 5
        assert limits.max_checkpoints == 100

    def test_custom_limits(self):
        limits = ResourceLimits(max_agents=2, max_steps_per_agent=5)
        assert limits.max_agents == 2
        assert limits.max_steps_per_agent == 5

    def test_limits_frozen(self):
        limits = ResourceLimits()
        with pytest.raises(AttributeError):
            limits.max_agents = 20

    def test_limits_to_dict(self):
        limits = ResourceLimits(max_agents=3)
        d = limits.to_dict()
        assert d["max_agents"] == 3
        assert d["max_concurrent_executions"] == 5


# ── TenantContext Tests ─────────────────────────────────────────────────


class TestTenantContext:
    def test_create_valid_context(self):
        ctx = TenantContext(tenant_id="t1", agent_id="a1")
        assert ctx.tenant_id == "t1"
        assert ctx.agent_id == "a1"
        assert ctx.is_valid

    def test_context_frozen(self):
        ctx = TenantContext(tenant_id="t1", agent_id="a1")
        with pytest.raises(AttributeError):
            ctx.tenant_id = "t2"

    def test_context_invalid_empty_tenant(self):
        ctx = TenantContext(tenant_id="", agent_id="a1")
        assert not ctx.is_valid

    def test_context_invalid_empty_agent(self):
        ctx = TenantContext(tenant_id="t1", agent_id="")
        assert not ctx.is_valid

    def test_context_has_capability_empty_restricted(self):
        """No allowed_capabilities = allow all."""
        ctx = TenantContext(tenant_id="t1", agent_id="a1")
        assert ctx.has_capability("anything")

    def test_context_has_capability_included(self):
        ctx = TenantContext(
            tenant_id="t1",
            agent_id="a1",
            allowed_capabilities=frozenset(["read", "write"]),
        )
        assert ctx.has_capability("read")
        assert ctx.has_capability("write")

    def test_context_has_capability_excluded(self):
        ctx = TenantContext(
            tenant_id="t1",
            agent_id="a1",
            allowed_capabilities=frozenset(["read"]),
        )
        assert not ctx.has_capability("execute")

    def test_context_with_resource_limits(self):
        limits = ResourceLimits(max_steps_per_agent=5)
        ctx = TenantContext(
            tenant_id="t1",
            agent_id="a1",
            resource_limits=limits,
        )
        assert ctx.resource_limits.max_steps_per_agent == 5

    def test_context_to_dict(self):
        ctx = TenantContext(
            tenant_id="t1",
            agent_id="a1",
            allowed_capabilities=frozenset(["cap1"]),
        )
        d = ctx.to_dict()
        assert d["tenant_id"] == "t1"
        assert d["agent_id"] == "a1"
        assert d["allowed_capabilities"] == ["cap1"]

    def test_context_immutability_enforcement(self):
        """TenantContext cannot be mutated after creation."""
        ctx = TenantContext(tenant_id="t1", agent_id="a1")
        with pytest.raises(AttributeError):
            ctx.tenant_id = "t2"
        with pytest.raises(AttributeError):
            ctx.agent_id = "a2"
