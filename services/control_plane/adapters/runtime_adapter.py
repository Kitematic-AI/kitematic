"""RuntimeExecutorAdapter — bridges StepCoordinator planning with ExecutionRuntime execution.

Flow:
  1. Coordinator plans step (EXECUTE/PAUSE/COMPLETE/FAIL)
  2. If EXECUTE: builds context, executes step via runtime
  3. Updates StateMachine on failure only
  4. Returns StepResponse

Responsibilities:
  - Translate StepPlan into ExecutionContext + StepRequest
  - Execute step via ExecutionRuntime interface
  - Report runtime failure to StateMachine (FAILED only)
  - Deep-copy input state to prevent mutation

Does NOT:
  - Decide lifecycle transitions (COMPLETE/PAUSE are coordinator decisions)
  - Import memory/checkpoint repository types (Any-typed for dependency inversion)
  - Persist data or make network calls
"""

import copy
from typing import Any

from runtime.contracts.step_request import StepRequest
from runtime.contracts.step_response import StepResponse, StepStatus
from runtime.execution.context_builder import ContextBuilder
from runtime.execution.execution_runtime import ExecutionRuntime
from services.control_plane.orchestrator.state_machine import ExecutionStateMachine, ExecutionStatus
from services.control_plane.orchestrator.step_coordinator import (
    StepAction,
    StepCoordinator,
    StepPlan,
)


class RuntimeExecutorAdapter:
    """Bridges StepCoordinator planning with ExecutionRuntime execution.

    Coordinates the flow between planning and execution:
      1. Plans the step via StepCoordinator
      2. Executes via ExecutionRuntime (if plan is EXECUTE)
      3. Notifies StateMachine on failure
    """

    def __init__(
        self,
        runtime: ExecutionRuntime,
        coordinator: StepCoordinator | None = None,
        memory: Any = None,
        checkpoint: Any = None,
    ) -> None:
        self._runtime = runtime
        self._coordinator = coordinator or StepCoordinator()
        self._memory = memory
        self._checkpoint = checkpoint

    async def plan_and_execute(
        self,
        execution_id: str,
        agent_id: str,
        goal: str,
        step_number: int,
        state: dict[str, Any],
        budget_remaining: float,
        allowed_tools: list[str],
        sm: ExecutionStateMachine,
    ) -> tuple[StepPlan, StepResponse | None]:
        """Plan a step and execute if the plan is EXECUTE.

        Returns (plan, response). response is None when plan is not EXECUTE.
        """
        plan = self._coordinator.plan_step(
            execution_id,
            step_number,
            goal,
            budget_remaining,
            allowed_tools,
        )

        if plan.action != StepAction.EXECUTE:
            return plan, None

        response = await self.execute_step(
            execution_id=execution_id,
            agent_id=agent_id,
            goal=goal,
            step_number=plan.step_number,
            state=state,
            budget_remaining=budget_remaining,
            allowed_tools=allowed_tools,
            sm=sm,
        )

        return plan, response

    async def execute_step(
        self,
        execution_id: str,
        agent_id: str,
        goal: str,
        step_number: int,
        state: dict[str, Any],
        budget_remaining: float,
        allowed_tools: list[str],
        sm: ExecutionStateMachine,
    ) -> StepResponse:
        """Execute a single step via the runtime.

        Transitions SM to FAILED on runtime failure only.
        """
        safe_state = copy.deepcopy(state)

        ctx = (
            ContextBuilder(execution_id, agent_id)
            .with_budget(int(budget_remaining))
            .with_step_number(step_number)
            .with_state(safe_state)
            .with_allowed_tools(allowed_tools)
            .with_memory(self._memory)
            .with_checkpoint(self._checkpoint)
            .build()
        )

        req = StepRequest(
            execution_id=execution_id,
            agent_id=agent_id,
            goal=goal,
            state=safe_state,
            allowed_tools=allowed_tools,
        )

        try:
            response = await self._runtime.execute_step(req, ctx)
        except Exception as exc:
            if sm.can_transition(ExecutionStatus.FAILED):
                sm.transition(
                    target=ExecutionStatus.FAILED,
                    reason=str(exc),
                    actor="runtime_adapter",
                )
            return StepResponse(
                status=StepStatus.FAILED,
                error_message=str(exc),
                tokens_consumed=0,
            )

        if response.status == StepStatus.FAILED:
            if sm.can_transition(ExecutionStatus.FAILED):
                sm.transition(
                    target=ExecutionStatus.FAILED,
                    reason=response.error_message or "step_execution_failed",
                    actor="runtime_adapter",
                )

        return response
