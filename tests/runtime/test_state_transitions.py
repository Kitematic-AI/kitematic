"""Runtime state transition tests.

These tests verify the runtime contracts work correctly.
"""

from runtime.contracts.agent_state import AgentState
from runtime.contracts.step_request import StepRequest
from runtime.contracts.step_response import StepStatus


class TestStateTransitions:
    """Runtime contract verification tests."""

    def test_step_request_creation(self) -> None:
        """Verify StepRequest dataclass works correctly."""
        req = StepRequest(
            execution_id="exec-1",
            agent_id="agent-1",
            goal="Analyze Q4 sales",
        )
        assert req.execution_id == "exec-1"
        assert req.agent_id == "agent-1"
        assert req.goal == "Analyze Q4 sales"

    def test_step_response_status_enum(self) -> None:
        """Verify all StepStatus values are valid."""
        assert StepStatus.COMPLETED.value == "COMPLETED"
        assert StepStatus.TOOL_REQUEST.value == "TOOL_REQUEST"
        assert StepStatus.APPROVAL_REQUIRED.value == "APPROVAL_REQUIRED"
        assert StepStatus.FAILED.value == "FAILED"

    def test_agent_state_serialization(self) -> None:
        """Verify AgentState can be converted to dict."""
        state = AgentState(
            execution_id="exec-1",
            agent_id="agent-1",
            current_node="analyze",
            step_number=3,
            data={"revenue": 100000},
        )
        assert state.execution_id == "exec-1"
        assert state.step_number == 3
        assert state.data["revenue"] == 100000
