"""Policy domain model — rules for authorization and governance."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class PolicyEffect(Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class PolicyStatus(Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    DEPRECATED = "DEPRECATED"


@dataclass(frozen=True)
class PolicyRule:
    """A single policy rule defining what is permitted or blocked."""

    policy_id: str
    tenant_id: str
    name: str
    target: str  # e.g. "mcp.database.*", "model.gpt-4"
    effect: PolicyEffect
    condition: str | None = None  # CEL expression
    priority: int = 100
    status: PolicyStatus = PolicyStatus.ACTIVE
    created_at: datetime | None = None
    updated_at: datetime | None = None
    required_capabilities: tuple[str, ...] = ()  # Capability IDs required for this rule

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.policy_id:
            errors.append("policy_id is required")
        if not self.target:
            errors.append("target is required (e.g. 'mcp.database.*')")
        if not self.name:
            errors.append("name is required")
        return errors

    @property
    def is_valid(self) -> bool:
        return len(self.validate()) == 0


@dataclass(frozen=True)
class PolicyEvaluation:
    """Result of evaluating an action against policy rules."""

    request_id: str
    decision: PolicyEffect
    matched_rule: str | None = None
    reason: str = ""
    audit_log_ref: str | None = None

    @property
    def is_allowed(self) -> bool:
        return self.decision == PolicyEffect.ALLOW

    @property
    def is_denied(self) -> bool:
        return self.decision == PolicyEffect.DENY

    @property
    def requires_approval(self) -> bool:
        return self.decision == PolicyEffect.REQUIRE_APPROVAL
