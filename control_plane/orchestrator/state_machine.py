"""State machine for Agent execution — single source of truth for all transitions.

Every transition is recorded as a StateTransition with:
  - from_state / to_state
  - reason (why)
  - actor (who initiated)
  - timestamp
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class ExecutionStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    RESUMING = "RESUMING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class StateTransition:
    """Immutable record of a single state transition."""

    from_state: ExecutionStatus
    to_state: ExecutionStatus
    reason: str
    actor: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


# Define all legal transitions
LEGAL_TRANSITIONS: dict[ExecutionStatus, set[ExecutionStatus]] = {
    ExecutionStatus.PENDING: {ExecutionStatus.RUNNING, ExecutionStatus.FAILED},
    ExecutionStatus.RUNNING: {
        ExecutionStatus.PAUSED,
        ExecutionStatus.COMPLETED,
        ExecutionStatus.FAILED,
    },
    ExecutionStatus.PAUSED: {ExecutionStatus.RESUMING, ExecutionStatus.FAILED},
    ExecutionStatus.RESUMING: {ExecutionStatus.RUNNING, ExecutionStatus.FAILED},
    ExecutionStatus.COMPLETED: set(),  # terminal
    ExecutionStatus.FAILED: set(),     # terminal
}


class InvalidTransitionError(Exception):
    """Raised when a state transition is not allowed."""

    def __init__(self, from_state: ExecutionStatus, to_state: ExecutionStatus):
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"Invalid transition: {from_state.value} → {to_state.value}"
        )


class ExecutionStateMachine:
    """Manages state transitions with causality tracking."""

    def __init__(self, initial_state: ExecutionStatus = ExecutionStatus.PENDING) -> None:
        self._current_state = initial_state
        self._history: list[StateTransition] = []

    @property
    def current_state(self) -> ExecutionStatus:
        return self._current_state

    @property
    def history(self) -> list[StateTransition]:
        return list(self._history)

    def can_transition(self, target: ExecutionStatus) -> bool:
        """Check if a transition to target state is legal."""
        return target in LEGAL_TRANSITIONS.get(self._current_state, set())

    def transition(
        self,
        target: ExecutionStatus,
        reason: str,
        actor: str,
        metadata: dict[str, Any] | None = None,
    ) -> StateTransition:
        """Execute a state transition. Raises InvalidTransitionError if illegal."""
        if not self.can_transition(target):
            raise InvalidTransitionError(self._current_state, target)

        record = StateTransition(
            from_state=self._current_state,
            to_state=target,
            reason=reason,
            actor=actor,
            metadata=metadata or {},
        )
        self._current_state = target
        self._history.append(record)
        return record
