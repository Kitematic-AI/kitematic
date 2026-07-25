"""Execution context — runtime state passed to each step execution."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionContext:
    """State carried across step executions within a single run.

    This is the runtime's view of execution — not the domain view.
    Contains only what the runtime needs to execute a single step.

    Optional references (memory, checkpoint) are injected by the orchestrator.
    Runtime uses them via their interface methods (save/get/list/search).
    """

    execution_id: str
    agent_id: str
    step_number: int

    state: dict[str, Any]

    budget_remaining: int
    tokens_per_step: int = 10

    allowed_tools: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # --- Phase 2D: optional references for checkpoint/memory integration ---
    # Typed as Any to avoid runtime→services dependency.
    # Actual type is CheckpointRepository | MemoryRepository (injected by orchestrator).
    tokens_consumed: int = 0
    memory: Any = None
    checkpoint: Any = None
