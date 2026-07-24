"""PolicyEngineAdapter — bridges ABI PolicyEvaluator to existing PolicyEngine.

Decomposes Intent → PolicyEngine params, parses dict result → tuple.
"""

from __future__ import annotations

from runtime.kitematic_runtime.runtime import Intent, PolicyEvaluator
from services.control_plane.policy.policy_engine import PolicyEngine


class PolicyEngineAdapter(PolicyEvaluator):
    """Concrete adapter: ABI PolicyEvaluator → PolicyEngine.

    Translates:
      - evaluate_intent(Intent) → evaluate(agent_id, action, resource)
      - check_capability(action, agent_id) → evaluate(agent_id, action, action)
    """

    def __init__(self, engine: PolicyEngine) -> None:
        self._engine = engine

    async def evaluate_intent(self, intent: Intent) -> tuple[bool, str | None]:
        """Evaluate whether an intent is permitted.

        Decomposes Intent into PolicyEngine parameters,
        parses dict result into (allowed, reason) tuple.
        Unknown/malformed results are treated as DENY (safe default).
        """
        result = await self._engine.evaluate(
            agent_id=intent.agent_id,
            action=intent.action,
            resource=intent.action,
        )

        decision = result.get("decision")
        if decision is None:
            return (False, "Malformed policy result: missing decision")

        if decision == "ALLOW":
            return (True, None)

        reason = result.get("reason", "Policy denied the intent")
        matched_rule = result.get("matched_rule")
        if matched_rule:
            reason = f"[{matched_rule}] {reason}"
        return (False, reason)

    async def check_capability(self, action: str, agent_id: str) -> tuple[bool, str | None]:
        """Check if agent has a capability for the given action.

        Delegates to PolicyEngine.evaluate() with action as resource.
        Unknown/malformed results are treated as DENY (safe default).
        """
        result = await self._engine.evaluate(
            agent_id=agent_id,
            action=action,
            resource=action,
        )

        decision = result.get("decision")
        if decision is None:
            return (False, "Malformed policy result: missing decision")

        if decision == "ALLOW":
            return (True, None)

        reason = result.get("reason", "Policy denied the capability")
        matched_rule = result.get("matched_rule")
        if matched_rule:
            reason = f"[{matched_rule}] {reason}"
        return (False, reason)
