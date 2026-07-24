"""LifecycleManager — manages Agent execution lifecycle.

Uses:
  - AgentRegistry (for state updates)
  - ExecutionStateMachine (for transitions)
  - StepCoordinator (for planning)

Does NOT:
  - Execute tools
  - Call LLMs
  - Make network calls
"""

from typing import Any

from services.control_plane.agent_registry.agent_registry import AgentRegistry
from services.control_plane.errors.orchestration_errors import (
    AgentInstanceNotFoundError,
)
from services.control_plane.orchestrator.state_machine import ExecutionStateMachine, ExecutionStatus


class LifecycleManager:
    """Manages start, stop, pause, resume for Agent executions."""

    def __init__(self, agent_registry: AgentRegistry) -> None:
        self._registry = agent_registry
        self._state_machines: dict[str, ExecutionStateMachine] = {}

    def _get_state_machine(self, execution_id: str) -> ExecutionStateMachine:
        if execution_id not in self._state_machines:
            self._state_machines[execution_id] = ExecutionStateMachine()
        return self._state_machines[execution_id]

    async def start_execution(
        self, instance_id: str, goal: str
    ) -> str:
        """Start a new execution. Returns execution_id."""
        instance = await self._registry.get_instance(instance_id)
        if instance is None:
            raise AgentInstanceNotFoundError(instance_id)

        execution_id = f"exec-{instance_id}"

        # Create state machine and transition to RUNNING (idempotent: skip if already running)
        sm = self._get_state_machine(execution_id)
        if sm.can_transition(ExecutionStatus.RUNNING):
            sm.transition(
                target=ExecutionStatus.RUNNING,
                reason="user_started",
                actor="lifecycle_manager",
                metadata={"instance_id": instance_id, "goal": goal},
            )

        return execution_id

    async def stop_execution(self, execution_id: str) -> None:
        """Stop execution permanently."""
        sm = self._get_state_machine(execution_id)
        if sm.current_state in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED):
            return  # already terminal

        # Force transition to FAILED (for stop, we treat it as a user-initiated termination)
        if sm.can_transition(ExecutionStatus.FAILED):
            sm.transition(
                target=ExecutionStatus.FAILED,
                reason="user_stopped",
                actor="lifecycle_manager",
            )

    async def pause_execution(self, execution_id: str) -> None:
        """Pause execution mid-step."""
        sm = self._get_state_machine(execution_id)
        if sm.can_transition(ExecutionStatus.PAUSED):
            sm.transition(
                target=ExecutionStatus.PAUSED,
                reason="user_paused",
                actor="lifecycle_manager",
            )

    async def resume_execution(self, execution_id: str) -> None:
        """Resume from last checkpoint."""
        sm = self._get_state_machine(execution_id)
        if sm.can_transition(ExecutionStatus.RESUMING):
            sm.transition(
                target=ExecutionStatus.RESUMING,
                reason="user_resumed",
                actor="lifecycle_manager",
            )
        if sm.can_transition(ExecutionStatus.RUNNING):
            sm.transition(
                target=ExecutionStatus.RUNNING,
                reason="step_execution_started",
                actor="orchestrator",
            )

    async def get_execution_status(self, execution_id: str) -> str:
        """Return current execution status."""
        sm = self._get_state_machine(execution_id)
        return sm.current_state.value

    def get_transition_history(self, execution_id: str) -> list[dict[str, Any]]:
        """Return full transition history for an execution."""
        sm = self._get_state_machine(execution_id)
        return [
            {
                "from_state": t.from_state.value,
                "to_state": t.to_state.value,
                "reason": t.reason,
                "actor": t.actor,
                "timestamp": t.timestamp.isoformat(),
            }
            for t in sm.history
        ]
