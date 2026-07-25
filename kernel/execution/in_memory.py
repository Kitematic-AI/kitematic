"""InMemoryRuntime — in-memory step executor for testing and development.

Simulates step execution by processing agent state transitions.
No LLM/MCP/network calls. Configurable token consumption.
"""

from datetime import UTC, datetime
from uuid import uuid4

from core.contracts.step_request import StepRequest
from core.contracts.step_response import StepResponse, StepStatus
from core.domain.checkpoint import Checkpoint, CheckpointTrigger
from kernel.execution.exceptions import (
    BudgetExceededError,
    InvalidStepRequestError,
)
from kernel.execution.context import ExecutionContext
from kernel.execution.runtime import ExecutionRuntime


class InMemoryRuntime(ExecutionRuntime):
    """In-memory step executor.

    Simulates execution by:
      - Validating the step request
      - Checking budget
      - Copying state and adding runtime metadata
      - Tracking token consumption
      - Auto-saving checkpoint if context.checkpoint is set
    """

    async def execute_step(
        self,
        request: StepRequest,
        context: ExecutionContext,
    ) -> StepResponse:
        """Execute one step in-memory.

        Does NOT mutate the input state — returns a copy with updates.
        """
        self._validate_request(request)
        self._check_budget(context)

        updated_state = dict(request.state)
        runtime_meta = updated_state.get("_runtime", {})
        steps_before = runtime_meta.get("steps_executed", 0)
        updated_state["_runtime"] = {
            "steps_executed": steps_before + 1,
            "last_node": f"step-{context.step_number}",
        }

        tokens = context.tokens_per_step
        context.tokens_consumed += tokens
        context.budget_remaining -= tokens

        response = StepResponse(
            status=StepStatus.COMPLETED,
            updated_state=updated_state,
            output=f"Step {context.step_number} executed for goal: {request.goal}",
            tokens_consumed=tokens,
        )

        if context.checkpoint is not None:
            checkpoint = Checkpoint(
                checkpoint_id=str(uuid4()),
                execution_id=context.execution_id,
                version=context.step_number,
                trigger_reason=CheckpointTrigger.STEP_COMPLETE,
                checkpoint_hash="auto",
                agent_state_ref=None,
                memory_refs=(),
                tool_history=(),
                created_at=datetime.now(UTC),
            )
            await context.checkpoint.save(checkpoint)

        return response

    def _validate_request(self, request: StepRequest) -> None:
        errors: list[str] = []
        if not request.execution_id:
            errors.append("execution_id is required")
        if not request.agent_id:
            errors.append("agent_id is required")
        if not request.goal:
            errors.append("goal is required")
        if errors:
            raise InvalidStepRequestError(errors)

    def _check_budget(self, context: ExecutionContext) -> None:
        if context.budget_remaining <= 0:
            raise BudgetExceededError(limit=0, consumed=0)
