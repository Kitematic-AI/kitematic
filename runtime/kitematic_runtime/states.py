"""Execution state machine for the Runtime Contract ABI.

Defines the lifecycle states and valid transitions for intent execution.
Enforced by KitematicRuntime to prevent invalid lifecycle states.

State Flow:
  CREATED → VALIDATING → AUTHORIZED → EXECUTING → CHECKPOINTING → COMPLETED
                                  ↓            ↓
                                FAILED       FAILED / HALTED
                            HALTED       HALTED

Any non-terminal state can transition to HALTED on unrecoverable error.
Terminal states (no outbound transitions): COMPLETED, FAILED, HALTED
"""

from enum import Enum


class RuntimeState(Enum):
    """Lifecycle states for the Runtime itself.

    RUNNING → DRAINING → STOPPED

    RUNNING:
      Accepts new executions normally.

    DRAINING:
      Rejects new executions (503 / RuntimeDrainingError).
      Allows in-flight executions to complete naturally.

    STOPPED:
      Rejects everything. All resources released.
    """

    RUNNING = "running"
    DRAINING = "draining"
    STOPPED = "stopped"


class ExecutionState(Enum):
    """Lifecycle states for intent execution."""

    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    AUTHORIZED = "AUTHORIZED"
    EXECUTING = "EXECUTING"
    CHECKPOINTING = "CHECKPOINTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    HALTED = "HALTED"


C = ExecutionState
VALID_TRANSITIONS: dict[ExecutionState, frozenset[ExecutionState]] = {
    C.CREATED: frozenset({C.VALIDATING}),
    C.VALIDATING: frozenset({C.AUTHORIZED, C.FAILED, C.HALTED}),
    C.AUTHORIZED: frozenset({C.EXECUTING, C.FAILED, C.HALTED}),
    C.EXECUTING: frozenset({C.CHECKPOINTING, C.FAILED, C.HALTED}),
    C.CHECKPOINTING: frozenset({C.COMPLETED, C.HALTED}),
    C.COMPLETED: frozenset(),
    C.FAILED: frozenset(),
    C.HALTED: frozenset(),
}


def is_valid_transition(current: ExecutionState, target: ExecutionState) -> bool:
    """Check if a state transition is valid."""
    return target in VALID_TRANSITIONS.get(current, frozenset())


def get_valid_transitions(current: ExecutionState) -> frozenset[ExecutionState]:
    """Get all valid target states from the current state."""
    return VALID_TRANSITIONS.get(current, frozenset())
