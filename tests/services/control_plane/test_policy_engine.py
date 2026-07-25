"""Tests for PolicyEngine — contract compliance + rule evaluation logic."""

import pytest

from control_plane.policy.engine import PolicyEngine, _target_matches
from core.policies.evaluator import PolicyEvaluator


class TestPolicyEngineImplementsPolicyEvaluator:
    """Verify PolicyEngine satisfies the PolicyEvaluator ABC contract."""

    @pytest.mark.asyncio
    async def test_isinstance_policy_evaluator(self) -> None:
        engine = PolicyEngine()
        assert isinstance(engine, PolicyEvaluator)

    @pytest.mark.asyncio
    async def test_evaluate_method_exists(self) -> None:
        engine = PolicyEngine()
        assert hasattr(engine, "evaluate")
        assert callable(getattr(engine, "evaluate"))

    @pytest.mark.asyncio
    async def test_create_policy_method_exists(self) -> None:
        engine = PolicyEngine()
        assert hasattr(engine, "create_policy")
        assert callable(getattr(engine, "create_policy"))

    @pytest.mark.asyncio
    async def test_list_policies_method_exists(self) -> None:
        engine = PolicyEngine()
        assert hasattr(engine, "list_policies")
        assert callable(getattr(engine, "list_policies"))

    @pytest.mark.asyncio
    async def test_evaluate_returns_dict(self) -> None:
        engine = PolicyEngine()
        result = await engine.evaluate("agent-1", "read", "mcp.database.read")
        assert isinstance(result, dict)
        assert "decision" in result
        assert "matched_rule" in result
        assert "reason" in result


class TestTargetMatching:
    def test_exact_match(self) -> None:
        assert _target_matches("mcp.database.read", "mcp.database.read") is True

    def test_exact_mismatch(self) -> None:
        assert _target_matches("mcp.database.write", "mcp.database.read") is False

    def test_prefix_wildcard_matches(self) -> None:
        assert _target_matches("mcp.database.*", "mcp.database.read") is True

    def test_prefix_wildcard_no_match(self) -> None:
        assert _target_matches("mcp.database.*", "mcp.file.read") is False

    def test_prefix_wildcard_exact_prefix(self) -> None:
        assert _target_matches("mcp.database.*", "mcp.database") is True

    def test_catch_all(self) -> None:
        assert _target_matches("*", "anything.goes.here") is True

    def test_no_wildcard_partial(self) -> None:
        assert _target_matches("mcp.database", "mcp.database.read") is False


class TestEvaluate:
    @pytest.mark.asyncio
    async def test_default_allow_when_no_rules(self) -> None:
        engine = PolicyEngine()
        result = await engine.evaluate("agent-1", "read", "mcp.database.read")
        assert result["decision"] == "ALLOW"
        assert result["matched_rule"] is None

    @pytest.mark.asyncio
    async def test_deny_matching_rule(self) -> None:
        engine = PolicyEngine()
        await engine.create_policy("block-gpt4", "model.gpt-4", "DENY")
        result = await engine.evaluate("agent-1", "call", "model.gpt-4")
        assert result["decision"] == "DENY"
        assert result["matched_rule"] is not None

    @pytest.mark.asyncio
    async def test_require_approval(self) -> None:
        engine = PolicyEngine()
        await engine.create_policy("approval-for-deletes", "mcp.database.delete", "REQUIRE_APPROVAL")
        result = await engine.evaluate("agent-1", "delete", "mcp.database.delete")
        assert result["decision"] == "REQUIRE_APPROVAL"

    @pytest.mark.asyncio
    async def test_priority_ordering(self) -> None:
        from core.policies.policy import PolicyEffect, PolicyRule, PolicyStatus

        engine = PolicyEngine()
        # low priority number = higher precedence
        allow_rule = PolicyRule(
            policy_id="pol-allow", tenant_id="default", name="low-pri-allow",
            target="mcp.*", effect=PolicyEffect.ALLOW, priority=200,
            status=PolicyStatus.ACTIVE,
        )
        deny_rule = PolicyRule(
            policy_id="pol-deny", tenant_id="default", name="high-pri-deny",
            target="mcp.database.*", effect=PolicyEffect.DENY, priority=100,
            status=PolicyStatus.ACTIVE,
        )
        engine._policies[allow_rule.policy_id] = allow_rule
        engine._policies[deny_rule.policy_id] = deny_rule
        result = await engine.evaluate("agent-1", "read", "mcp.database.read")
        assert result["decision"] == "DENY"

    @pytest.mark.asyncio
    async def test_ignores_inactive_rules(self) -> None:
        from core.policies.policy import PolicyEffect, PolicyRule, PolicyStatus

        engine = PolicyEngine()
        inactive_rule = PolicyRule(
            policy_id="pol-inactive", tenant_id="default", name="old-rule",
            target="mcp.database.*", effect=PolicyEffect.DENY, priority=100,
            status=PolicyStatus.INACTIVE,
        )
        engine._policies[inactive_rule.policy_id] = inactive_rule
        result = await engine.evaluate("agent-1", "read", "mcp.database.read")
        assert result["decision"] == "ALLOW"

    @pytest.mark.asyncio
    async def test_wildcard_match(self) -> None:
        engine = PolicyEngine()
        await engine.create_policy("block-all-model", "model.*", "DENY")
        result = await engine.evaluate("agent-1", "call", "model.gpt-4")
        assert result["decision"] == "DENY"

    @pytest.mark.asyncio
    async def test_no_match_returns_allow(self) -> None:
        engine = PolicyEngine()
        await engine.create_policy("block-gpt4", "model.gpt-4", "DENY")
        result = await engine.evaluate("agent-1", "read", "mcp.database.read")
        assert result["decision"] == "ALLOW"

    @pytest.mark.asyncio
    async def test_reason_contains_rule_name(self) -> None:
        engine = PolicyEngine()
        await engine.create_policy("block-public", "model.gpt-4", "DENY")
        result = await engine.evaluate("agent-1", "call", "model.gpt-4")
        assert "block-public" in result["reason"]


class TestCreatePolicy:
    @pytest.mark.asyncio
    async def test_returns_policy_id(self) -> None:
        engine = PolicyEngine()
        pid = await engine.create_policy("test-rule", "mcp.*", "ALLOW")
        assert pid.startswith("pol-")
        assert len(pid) > 4

    @pytest.mark.asyncio
    async def test_policy_appears_in_list(self) -> None:
        engine = PolicyEngine()
        await engine.create_policy("test-rule", "mcp.*", "ALLOW")
        policies = await engine.list_policies()
        assert len(policies) == 1
        assert policies[0]["name"] == "test-rule"

    @pytest.mark.asyncio
    async def test_multiple_policies(self) -> None:
        engine = PolicyEngine()
        await engine.create_policy("rule-1", "mcp.*", "ALLOW")
        await engine.create_policy("rule-2", "model.*", "DENY")
        policies = await engine.list_policies()
        assert len(policies) == 2


class TestListPolicies:
    @pytest.mark.asyncio
    async def test_empty_when_no_policies(self) -> None:
        engine = PolicyEngine()
        assert await engine.list_policies() == []

    @pytest.mark.asyncio
    async def test_returns_all_fields(self) -> None:
        engine = PolicyEngine()
        await engine.create_policy("test", "mcp.*", "ALLOW")
        policies = await engine.list_policies()
        p = policies[0]
        assert all(k in p for k in ("policy_id", "name", "target", "effect", "priority", "status"))
