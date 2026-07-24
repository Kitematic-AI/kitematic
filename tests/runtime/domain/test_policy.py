"""Tests for Policy domain model."""

from runtime.domain.policy import (
    PolicyEffect,
    PolicyEvaluation,
    PolicyRule,
)


class TestPolicyRule:
    def test_valid_policy_passes_validation(self) -> None:
        rule = PolicyRule(
            policy_id="pol-123",
            tenant_id="tenant-abc",
            name="block-public-llm",
            target="model.gpt-4",
            effect=PolicyEffect.DENY,
        )
        errors = rule.validate()
        assert len(errors) == 0
        assert rule.is_valid is True

    def test_missing_required_fields_fails(self) -> None:
        rule = PolicyRule(
            policy_id="",
            tenant_id="tenant-abc",
            name="",
            target="",
            effect=PolicyEffect.ALLOW,
        )
        errors = rule.validate()
        assert len(errors) >= 3
        assert rule.is_valid is False

    def test_all_effects(self) -> None:
        assert PolicyEffect.ALLOW.value == "ALLOW"
        assert PolicyEffect.DENY.value == "DENY"
        assert PolicyEffect.REQUIRE_APPROVAL.value == "REQUIRE_APPROVAL"


class TestPolicyEvaluation:
    def test_allowed(self) -> None:
        ev = PolicyEvaluation(
            request_id="req-1",
            decision=PolicyEffect.ALLOW,
        )
        assert ev.is_allowed is True
        assert ev.is_denied is False
        assert ev.requires_approval is False

    def test_denied(self) -> None:
        ev = PolicyEvaluation(
            request_id="req-2",
            decision=PolicyEffect.DENY,
            matched_rule="pol-block",
            reason="User is not authorized",
        )
        assert ev.is_allowed is False
        assert ev.is_denied is True

    def test_requires_approval(self) -> None:
        ev = PolicyEvaluation(
            request_id="req-3",
            decision=PolicyEffect.REQUIRE_APPROVAL,
        )
        assert ev.requires_approval is True
