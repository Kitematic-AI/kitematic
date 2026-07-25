"""PolicyEngine — in-memory, rule-based policy evaluation.

Implements the PolicyEvaluator ABC. Rules are matched by resource target:
  1. Exact match (target == resource)
  2. Prefix wildcard (target = "mcp.database.*" -> matches "mcp.database.read")
  3. Catch-all (target = "*")

Priority ordering: lower priority number = higher precedence.
Default decision when no rule matches: ALLOW.
"""

import hashlib
import uuid
from typing import Any

from core.policies.policy import PolicyEffect, PolicyRule, PolicyStatus
from control_plane.policy.cache import InMemoryPolicyCache
from core.policies.capability_registry import CapabilityRegistry
from core.policies.evaluator import PolicyEvaluator


class PolicyEngine(PolicyEvaluator):
    """In-memory policy evaluation engine with optional capability awareness."""

    def __init__(
        self,
        capability_registry: CapabilityRegistry | None = None,
    ) -> None:
        self._policies: dict[str, PolicyRule] = {}
        self._capability_registry = capability_registry
        self._cache = InMemoryPolicyCache(ttl_seconds=300, max_entries=10_000)

    def _make_cache_key(
        self,
        agent_id: str,
        action: str,
        resource: str,
        required_capabilities: frozenset[str] | None,
    ) -> str:
        key_parts = [agent_id, action, resource]
        if required_capabilities:
            sorted_caps = sorted(required_capabilities)
            caps_hash = hashlib.sha256(",".join(sorted_caps).encode()).hexdigest()[:16]
            key_parts.append(caps_hash)
        else:
            key_parts.append("")
        return "|".join(key_parts)

    async def evaluate(
        self,
        agent_id: str,
        action: str,
        resource: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Evaluate whether an action is permitted.

        Finds all active rules whose target matches the resource, returns
        the highest-priority (lowest number) match. If no match -> ALLOW.
        """
        cache_key = self._make_cache_key(agent_id, action, resource, None)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        matching_rules: list = []
        for rule in self._policies.values():
            if rule.status != PolicyStatus.ACTIVE:
                continue
            if _target_matches(rule.target, resource):
                matching_rules.append(rule)

        if not matching_rules:
            result = {
                "decision": "ALLOW",
                "matched_rule": None,
                "reason": "No matching policy rule found",
            }
        else:
            matching_rules.sort(key=lambda r: r.priority)
            best = matching_rules[0]
            result = {
                "decision": best.effect.value,
                "matched_rule": best.policy_id,
                "reason": f"Matched rule: {best.name}",
            }

        self._cache.set(cache_key, result)
        return result

    async def evaluate_with_capabilities(
        self,
        agent_id: str,
        action: str,
        resource: str,
        required_capabilities: frozenset[str],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Evaluate whether an action is permitted with capability validation.

        This method first validates that all required capabilities are registered
        in the CapabilityRegistry, then delegates to the standard evaluation logic.
        """
        # 1. Capability registry validation (fail fast for missing capabilities)
        required_caps = frozenset(required_capabilities)
        if self._capability_registry is not None:
            for cap_id in required_capabilities:
                if not self._capability_registry.contains(cap_id):
                    return {
                        "decision": "DENY",
                        "matched_rule": None,
                        "reason": f"Capability not registered: {cap_id}",
                    }

        # Cache key for this evaluation
        cache_key = self._make_cache_key("", "", resource, frozenset(required_capabilities))
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        # 2. Standard policy evaluation (unchanged logic)
        matching_rules: list = []
        for rule in self._policies.values():
            if rule.status != PolicyStatus.ACTIVE:
                continue
            if _target_matches(rule.target, resource):
                # Also check rule-level required capabilities
                if rule.required_capabilities:
                    if not self._capability_registry:
                        return {
                            "decision": "DENY",
                            "matched_rule": None,
                            "reason": "Capability registry not available for capability validation",
                        }
                    for cap_id in rule.required_capabilities:
                        if not self._capability_registry.contains(cap_id):
                            return {
                                "decision": "DENY",
                                "matched_rule": None,
                                "reason": f"Capability not registered: {cap_id}",
                            }

                matching_rules.append(rule)

        if not matching_rules:
            result = {
                "decision": "ALLOW",
                "matched_rule": None,
                "reason": "No matching policy rule found",
            }
        else:
            matching_rules.sort(key=lambda r: r.priority)
            best = matching_rules[0]
            result = {
                "decision": best.effect.value,
                "matched_rule": best.policy_id,
                "reason": f"Matched rule: {best.name}",
            }

        # Cache the result
        self._cache.set(cache_key, result)
        return result

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
            effect=PolicyEffect(effect),
            condition=condition,
            status=PolicyStatus.ACTIVE,
        )
        self._policies[policy_id] = rule
        # Invalidate cache on policy creation
        self._cache.invalidate()
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
