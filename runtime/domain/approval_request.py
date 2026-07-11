"""ApprovalRequest domain model — Human-in-the-Loop approval workflow."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class ApprovalStatus(Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class RiskLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class ApprovalRequest:
    """A request for human approval before executing a sensitive action."""

    approval_id: str
    execution_id: str
    agent_instance_id: str
    action: str  # e.g. "send_mass_email", "delete_records"
    risk_level: RiskLevel
    status: ApprovalStatus = ApprovalStatus.PENDING
    reason: str = ""
    payload: str = ""  # JSON snapshot of what the Agent wants to do
    approved_by: str | None = None  # user_id
    rejection_reason: str | None = None
    expires_at: datetime | None = None
    created_at: datetime | None = None
    decided_at: datetime | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.approval_id:
            errors.append("approval_id is required")
        if not self.execution_id:
            errors.append("execution_id is required")
        if not self.action:
            errors.append("action is required")
        return errors

    @property
    def is_valid(self) -> bool:
        return len(self.validate()) == 0

    @property
    def is_decided(self) -> bool:
        return self.status in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED)

    @property
    def is_expired(self) -> bool:
        if self.expires_at and self.created_at:
            return datetime.now(timezone.utc) > self.expires_at
        return False
