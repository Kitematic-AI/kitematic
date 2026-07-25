"""Execution domain model — the lifecycle and state of an Agent execution."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ExecutionStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class BudgetConsumed:
    """Resource usage tracking for an execution."""
    tokens: int = 0
    cost_usd: float = 0.0
    time_ms: int = 0


@dataclass(frozen=True)
class ExecutionStep:
    """A single step within an execution."""
    step_number: int
    node_name: str
    runtime: str
    input_state_hash: str | None = None
    output_state_hash: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True)
class Execution:
    """An Agent execution — a single run from start to completion."""

    execution_id: str
    tenant_id: str
    agent_instance_id: str
    agent_manifest_version: str
    status: ExecutionStatus
    goal: str
    steps: tuple[ExecutionStep, ...] = ()
    budget_consumed: BudgetConsumed = field(default_factory=BudgetConsumed)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.execution_id:
            errors.append("execution_id is required")
        if not self.agent_instance_id:
            errors.append("agent_instance_id is required")
        if not self.goal:
            errors.append("goal is required")
        return errors

    @property
    def is_valid(self) -> bool:
        return len(self.validate()) == 0

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def total_tokens(self) -> int:
        return self.budget_consumed.tokens

    @property
    def total_cost(self) -> float:
        return self.budget_consumed.cost_usd

    @property
    def duration_ms(self) -> int:
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds() * 1000)
        return 0
