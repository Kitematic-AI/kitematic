"""Execution context — runtime state passed to each step execution."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionContext:
    """State carried across step executions within a single run.

    This is the runtime's view of execution — not the domain view.
    Contains only what the runtime needs to execute a single step.
    """

    execution_id: str
    agent_id: str
    step_number: int

    state: dict[str, Any]

    budget_remaining: int
    tokens_per_step: int = 10

    allowed_tools: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
