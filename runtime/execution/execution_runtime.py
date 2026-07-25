"""Execution runtime interface — the contract for step execution engines."""

from abc import ABC, abstractmethod

from core.contracts.step_request import StepRequest
from core.contracts.step_response import StepResponse
from runtime.execution.execution_context import ExecutionContext


class ExecutionRuntime(ABC):
    """Interface for step execution engines.

    Responsibilities:
      - Execute a single step given a StepRequest and ExecutionContext
      - Return a StepResponse with status + updated state
      - Track resource consumption (tokens)

    Does NOT:
      - Transition the StateMachine (Control Plane's role)
      - Make network calls or call LLMs
      - Modify external state
    """

    @abstractmethod
    async def execute_step(
        self,
        request: StepRequest,
        context: ExecutionContext,
    ) -> StepResponse:
        """Execute one step. Returns StepResponse with status + updated_state."""
        ...
