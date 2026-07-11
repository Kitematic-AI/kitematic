"""Tests for ExecutionStateMachine — the single source of truth for state transitions."""

import pytest
from services.control_plane.orchestrator.state_machine import (
    ExecutionStatus,
    ExecutionStateMachine,
    InvalidTransitionError,
)


class TestStateMachineTransitions:
    """Verify all legal and illegal transitions."""

    def test_initial_state_is_pending(self) -> None:
        sm = ExecutionStateMachine()
        assert sm.current_state == ExecutionStatus.PENDING

    def test_pending_to_running(self) -> None:
        sm = ExecutionStateMachine()
        record = sm.transition(
            target=ExecutionStatus.RUNNING,
            reason="user_started",
            actor="lifecycle_manager",
        )
        assert sm.current_state == ExecutionStatus.RUNNING
        assert record.from_state == ExecutionStatus.PENDING
        assert record.to_state == ExecutionStatus.RUNNING
        assert record.reason == "user_started"
        assert record.actor == "lifecycle_manager"
        assert record.timestamp is not None

    def test_running_to_paused(self) -> None:
        sm = ExecutionStateMachine(ExecutionStatus.RUNNING)
        sm.transition(target=ExecutionStatus.PAUSED, reason="approval_needed", actor="orchestrator")
        assert sm.current_state == ExecutionStatus.PAUSED

    def test_paused_to_resuming_to_running(self) -> None:
        sm = ExecutionStateMachine(ExecutionStatus.PAUSED)
        sm.transition(target=ExecutionStatus.RESUMING, reason="approved", actor="user")
        sm.transition(target=ExecutionStatus.RUNNING, reason="step_started", actor="orchestrator")
        assert sm.current_state == ExecutionStatus.RUNNING

    def test_running_to_completed(self) -> None:
        sm = ExecutionStateMachine(ExecutionStatus.RUNNING)
        sm.transition(target=ExecutionStatus.COMPLETED, reason="goal_reached", actor="orchestrator")
        assert sm.current_state == ExecutionStatus.COMPLETED

    def test_running_to_failed(self) -> None:
        sm = ExecutionStateMachine(ExecutionStatus.RUNNING)
        sm.transition(target=ExecutionStatus.FAILED, reason="irrecoverable_error", actor="orchestrator")
        assert sm.current_state == ExecutionStatus.FAILED

    def test_pending_to_failed(self) -> None:
        sm = ExecutionStateMachine()
        sm.transition(target=ExecutionStatus.FAILED, reason="validation_failed", actor="orchestrator")
        assert sm.current_state == ExecutionStatus.FAILED

    def test_paused_to_failed(self) -> None:
        sm = ExecutionStateMachine(ExecutionStatus.PAUSED)
        sm.transition(target=ExecutionStatus.FAILED, reason="timeout", actor="system")
        assert sm.current_state == ExecutionStatus.FAILED

    def test_completed_is_terminal(self) -> None:
        sm = ExecutionStateMachine(ExecutionStatus.COMPLETED)
        with pytest.raises(InvalidTransitionError):
            sm.transition(target=ExecutionStatus.RUNNING, reason="bad", actor="test")

    def test_failed_is_terminal(self) -> None:
        sm = ExecutionStateMachine(ExecutionStatus.FAILED)
        with pytest.raises(InvalidTransitionError):
            sm.transition(target=ExecutionStatus.RUNNING, reason="bad", actor="test")

    def test_pending_to_paused_is_illegal(self) -> None:
        sm = ExecutionStateMachine()
        with pytest.raises(InvalidTransitionError):
            sm.transition(target=ExecutionStatus.PAUSED, reason="bad", actor="test")

    def test_running_to_pending_is_illegal(self) -> None:
        sm = ExecutionStateMachine(ExecutionStatus.RUNNING)
        with pytest.raises(InvalidTransitionError):
            sm.transition(target=ExecutionStatus.PENDING, reason="bad", actor="test")


class TestStateMachineHistory:
    """Verify transition history tracking."""

    def test_history_records_all_transitions(self) -> None:
        sm = ExecutionStateMachine()
        sm.transition(target=ExecutionStatus.RUNNING, reason="start", actor="user")
        sm.transition(target=ExecutionStatus.PAUSED, reason="pause", actor="user")
        sm.transition(target=ExecutionStatus.RESUMING, reason="resume", actor="user")
        sm.transition(target=ExecutionStatus.RUNNING, reason="restart", actor="orchestrator")
        sm.transition(target=ExecutionStatus.COMPLETED, reason="done", actor="orchestrator")

        history = sm.history
        assert len(history) == 5
        assert history[0].to_state == ExecutionStatus.RUNNING
        assert history[4].to_state == ExecutionStatus.COMPLETED

    def test_history_is_immutable_copy(self) -> None:
        sm = ExecutionStateMachine()
        sm.transition(target=ExecutionStatus.RUNNING, reason="start", actor="user")
        history1 = sm.history
        sm.transition(target=ExecutionStatus.COMPLETED, reason="done", actor="orchestrator")
        history2 = sm.history
        assert len(history1) == 1
        assert len(history2) == 2

    def test_transition_with_metadata(self) -> None:
        sm = ExecutionStateMachine()
        record = sm.transition(
            target=ExecutionStatus.RUNNING,
            reason="user_started",
            actor="lifecycle_manager",
            metadata={"instance_id": "inst-1", "goal": "test"},
        )
        assert record.metadata["instance_id"] == "inst-1"
        assert record.metadata["goal"] == "test"
