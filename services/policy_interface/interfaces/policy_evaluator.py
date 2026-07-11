"""Policy evaluator interface — authorization and governance engine."""

from abc import ABC, abstractmethod
from typing import Any


class PolicyEvaluator(ABC):
    """Interface for policy evaluation."""

    @abstractmethod
    async def evaluate(
        self,
        agent_id: str,
        action: str,
        resource: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Evaluate whether an action is permitted.

        Returns a PolicyDecision dict with keys:
          - decision: ALLOW | DENY | REQUIRE_APPROVAL
          - matched_rule: str | None
          - reason: str
        """
        ...

    @abstractmethod
    async def create_policy(
        self,
        name: str,
        target: str,
        effect: str,
        condition: str | None = None,
    ) -> str:
        """Create a new policy rule. Returns policy_id."""
        ...

    @abstractmethod
    async def list_policies(self) -> list[dict[str, Any]]:
        """List all active policies for the current tenant."""
        ...
