"""PolicyEngine — in-memory, rule-based policy evaluation.

Implements the PolicyEvaluator ABC. Rules are matched by resource target:
  1. Exact match (target == resource)
  2. Prefix wildcard (target = "mcp.database.*" → matches "mcp.database.read")
  3. Catch-all (target = "*")

Priority ordering: lower priority number = higher precedence.
Default decision when no rule matches: ALLOW.
"""

import uuid
from typing import Any

from services.policy_interface.interfaces.policy_evaluator import PolicyEvaluator
from runtime.domain.policy import PolicyEffect, PolicyRule, PolicyStatus


def _generate_policy_id() -> str:
    return f"pol-{uuid.uuid4().hex[:12]}"


def _target_matches(target: str, resource: str) -> bool:
    """Check if a policy target matches the given resource."""
    if target == "*":
        return True
    if target.endswith(".*"):
        prefix = target[:-2]
        return resource == prefix or resource.startswith(prefix + ".")
    return target == resource


class PolicyEngine(PolicyEvaluator):
    """In-memory policy evaluation engine."""

    def __init__(self) -> None:
        self._policies: dict[str, PolicyRule] = {}

    async def evaluate(
        self,
        agent_id: str,
        action: str,
        resource: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Evaluate whether an action is permitted.

        Finds all active rules whose target matches the resource, returns
        the highest-priority (lowest number) match. If no match → ALLOW.
        """
        matching_rules: list[PolicyRule] = []
        for rule in self._policies.values():
            if rule.status != PolicyStatus.ACTIVE:
                continue
            if _target_matches(rule.target, resource):
                matching_rules.append(rule)

        if not matching_rules:
            return {
                "decision": PolicyEffect.ALLOW.value,
                "matched_rule": None,
                "reason": "No matching policy rule found",
            }

        matching_rules.sort(key=lambda r: r.priority)
        best = matching_rules[0]
        return {
            "decision": best.effect.value,
            "matched_rule": best.policy_id,
            "reason": f"Matched rule: {best.name}",
        }

    async def create_policy(
        self,
        name: str,
        target: str,
        effect: str,
        condition: str | None = None,
    ) -> str:
        """Create a new policy rule. Returns the new policy_id."""
        policy_id = _generate_policy_id()
        effect_enum = PolicyEffect(effect)
        rule = PolicyRule(
            policy_id=policy_id,
            tenant_id="default",
            name=name,
            target=target,
            effect=effect_enum,
            condition=condition,
            status=PolicyStatus.ACTIVE,
        )
        self._policies[policy_id] = rule
        return policy_id

    async def list_policies(self) -> list[dict[str, Any]]:
        """List all active policies."""
        return [
            {
                "policy_id": r.policy_id,
                "name": r.name,
                "target": r.target,
                "effect": r.effect.value,
                "priority": r.priority,
                "status": r.status.value,
            }
            for r in self._policies.values()
        ]
