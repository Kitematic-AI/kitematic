"""Step coordinator — plans and coordinates step execution without actually running tools.

Responsibilities:
  - Validate step prerequisites
  - Check execution state
  - Request policy decision
  - Emit execution request

Explicitly NOT responsible for:
  - Running tools
  - Calling LLMs
  - Executing commands
  - Network calls
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class StepAction(Enum):
    """Possible outcomes of step coordination."""

    EXECUTE = "EXECUTE"
    PAUSE_FOR_APPROVAL = "PAUSE_FOR_APPROVAL"
    CHECKPOINT = "CHECKPOINT"
    COMPLETE = "COMPLETE"
    FAIL = "FAIL"


@dataclass(frozen=True)
class StepPlan:
    """A planned step — the output of coordination."""

    action: StepAction
    execution_id: str
    step_number: int
    reason: str
    metadata: dict[str, Any] | None = None


class StepCoordinator:
    """Plans step execution without running anything.

    This is a pure coordination layer. The actual execution
    (LLM calls, tool runs) happens elsewhere.
    """

    def __init__(self, max_steps: int = 100) -> None:
        self._max_steps = max_steps

    def plan_step(
        self,
        execution_id: str,
        step_number: int,
        goal: str,
        budget_remaining: float,
        allowed_tools: list[str],
    ) -> StepPlan:
        """Plan the next step based on current context.

        This method does NOT execute anything. It only decides
        what should happen next.
        """
        # Check step limit
        if step_number >= self._max_steps:
            return StepPlan(
                action=StepAction.COMPLETE,
                execution_id=execution_id,
                step_number=step_number,
                reason="max_steps_reached",
            )

        # Check budget
        if budget_remaining <= 0:
            return StepPlan(
                action=StepAction.PAUSE_FOR_APPROVAL,
                execution_id=execution_id,
                step_number=step_number,
                reason="budget_exceeded",
            )

        # Check if tools are available
        if not allowed_tools:
            return StepPlan(
                action=StepAction.COMPLETE,
                execution_id=execution_id,
                step_number=step_number,
                reason="no_tools_available",
            )

        # Default: execute the step
        return StepPlan(
            action=StepAction.EXECUTE,
            execution_id=execution_id,
            step_number=step_number,
            reason="ready_to_execute",
        )

    def validate_step_prerequisites(
        self,
        current_state: str,
        step_number: int,
        max_steps: int,
    ) -> tuple[bool, str]:
        """Validate that a step can be taken.

        Returns (is_valid, reason).
        """
        if current_state not in ("RUNNING", "RESUMING"):
            return False, f"Cannot execute step in state: {current_state}"

        if step_number >= max_steps:
            return False, "Step limit exceeded"

        return True, "prerequisites_met"
