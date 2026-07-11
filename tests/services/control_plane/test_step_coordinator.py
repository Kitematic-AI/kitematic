"""Tests for StepCoordinator — planning and coordination only."""

import pytest
from services.control_plane.orchestrator.step_coordinator import StepCoordinator, StepAction


class TestStepCoordinatorPlanning:
    """Test step planning decisions."""

    def test_plan_step_execute_when_ready(self) -> None:
        coord = StepCoordinator(max_steps=100)
        plan = coord.plan_step(
            execution_id="exec-1",
            step_number=5,
            goal="analyze sales",
            budget_remaining=10.0,
            allowed_tools=["salesforce.read"],
        )
        assert plan.action == StepAction.EXECUTE
        assert plan.reason == "ready_to_execute"

    def test_plan_step_complete_when_max_steps_reached(self) -> None:
        coord = StepCoordinator(max_steps=100)
        plan = coord.plan_step(
            execution_id="exec-1",
            step_number=100,
            goal="analyze sales",
            budget_remaining=10.0,
            allowed_tools=["salesforce.read"],
        )
        assert plan.action == StepAction.COMPLETE
        assert plan.reason == "max_steps_reached"

    def test_plan_step_pause_when_budget_exceeded(self) -> None:
        coord = StepCoordinator(max_steps=100)
        plan = coord.plan_step(
            execution_id="exec-1",
            step_number=5,
            goal="analyze sales",
            budget_remaining=0.0,
            allowed_tools=["salesforce.read"],
        )
        assert plan.action == StepAction.PAUSE_FOR_APPROVAL
        assert plan.reason == "budget_exceeded"

    def test_plan_step_complete_when_no_tools(self) -> None:
        coord = StepCoordinator(max_steps=100)
        plan = coord.plan_step(
            execution_id="exec-1",
            step_number=5,
            goal="analyze sales",
            budget_remaining=10.0,
            allowed_tools=[],
        )
        assert plan.action == StepAction.COMPLETE
        assert plan.reason == "no_tools_available"


class TestStepCoordinatorValidation:
    """Test step prerequisite validation."""

    def test_validate_running_state(self) -> None:
        coord = StepCoordinator(max_steps=100)
        is_valid, reason = coord.validate_step_prerequisites(
            current_state="RUNNING",
            step_number=5,
            max_steps=100,
        )
        assert is_valid is True
        assert reason == "prerequisites_met"

    def test_validate_resuming_state(self) -> None:
        coord = StepCoordinator(max_steps=100)
        is_valid, reason = coord.validate_step_prerequisites(
            current_state="RESUMING",
            step_number=5,
            max_steps=100,
        )
        assert is_valid is True

    def test_validate_pending_state_fails(self) -> None:
        coord = StepCoordinator(max_steps=100)
        is_valid, reason = coord.validate_step_prerequisites(
            current_state="PENDING",
            step_number=5,
            max_steps=100,
        )
        assert is_valid is False
        assert "PENDING" in reason

    def test_validate_paused_state_fails(self) -> None:
        coord = StepCoordinator(max_steps=100)
        is_valid, reason = coord.validate_step_prerequisites(
            current_state="PAUSED",
            step_number=5,
            max_steps=100,
        )
        assert is_valid is False

    def test_validate_step_limit_exceeded(self) -> None:
        coord = StepCoordinator(max_steps=100)
        is_valid, reason = coord.validate_step_prerequisites(
            current_state="RUNNING",
            step_number=100,
            max_steps=100,
        )
        assert is_valid is False
        assert "limit" in reason.lower()
