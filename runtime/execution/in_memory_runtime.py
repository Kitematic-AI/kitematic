"""InMemoryRuntime — in-memory step executor for testing and development.

Simulates step execution by processing agent state transitions.
No LLM/MCP/network calls. Configurable token consumption.
"""

from runtime.contracts.step_request import StepRequest
from runtime.contracts.step_response import StepResponse, StepStatus
from runtime.execution.execution_context import ExecutionContext
from runtime.execution.execution_runtime import ExecutionRuntime
from runtime.execution.exceptions import (
    BudgetExceededError,
    InvalidStepRequestError,
)


class InMemoryRuntime(ExecutionRuntime):
    """In-memory step executor.

    Simulates execution by:
      - Validating the step request
      - Checking budget
      - Copying state and adding runtime metadata
      - Tracking token consumption
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

        return StepResponse(
            status=StepStatus.COMPLETED,
            updated_state=updated_state,
            output=f"Step {context.step_number} executed for goal: {request.goal}",
            tokens_consumed=tokens,
        )

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
