"""Tests for execution tracing."""

import time

import pytest

from runtime.kitematic_runtime.observability.tracing import (
    ExecutionTracer,
    TraceEntry,
    TracePhase,
)


class TestTraceEntry:
    """Tests for the TraceEntry frozen dataclass."""

    def test_to_dict_includes_all_fields(self):
        entry = TraceEntry(
            phase=TracePhase.POLICY_EVALUATION,
            start_time=100.0,
            end_time=200.0,
            duration_ms=100.0,
            success=True,
        )
        data = entry.to_dict()
        assert data["phase"] == "policy.evaluation"
        assert data["success"] is True
        assert data["duration_ms"] == 100.0

    def test_to_dict_includes_error(self):
        entry = TraceEntry(
            phase=TracePhase.POLICY_EVALUATION,
            start_time=100.0,
            end_time=200.0,
            duration_ms=100.0,
            success=False,
            error="Policy denied",
        )
        data = entry.to_dict()
        assert data["error"] == "Policy denied"
        assert data["success"] is False


class TestExecutionTracerPhases:
    """Tests for individual phase management."""

    def test_start_and_end_phase(self):
        tracer = ExecutionTracer(execution_id="exec-1")
        tracer.start_phase(TracePhase.POLICY_EVALUATION)
        time.sleep(0.001)
        entry = tracer.end_phase(success=True)

        assert entry.phase == TracePhase.POLICY_EVALUATION
        assert entry.success is True
        assert entry.duration_ms > 0

    def test_end_phase_with_error(self):
        tracer = ExecutionTracer(execution_id="exec-1")
        tracer.start_phase(TracePhase.TOOL_EXECUTION)
        entry = tracer.end_phase(success=False, error="MCP connection failed")

        assert entry.success is False
        assert entry.error == "MCP connection failed"

    def test_end_phase_without_start_raises(self):
        tracer = ExecutionTracer(execution_id="exec-1")

        with pytest.raises(RuntimeError, match="No active phase"):
            tracer.end_phase()

    def test_start_phase_auto_ends_previous(self):
        tracer = ExecutionTracer(execution_id="exec-1")
        tracer.start_phase(TracePhase.POLICY_EVALUATION)
        tracer.start_phase(TracePhase.TOOL_EXECUTION)
        entry = tracer.end_phase(success=True)

        # Both phases should be recorded
        trace = tracer.get_trace()
        assert len(trace) == 2
        assert trace[0]["phase"] == "policy.evaluation"
        assert trace[1]["phase"] == "tool.execution"

    def test_phase_metadata(self):
        tracer = ExecutionTracer(execution_id="exec-1")
        tracer.start_phase(
            TracePhase.POLICY_EVALUATION,
            metadata={"matched_rules": 3},
        )
        entry = tracer.end_phase(success=True)

        assert entry.metadata == {"matched_rules": 3}


class TestExecutionTracerTrace:
    """Tests for trace collection."""

    def test_get_trace_returns_list(self):
        tracer = ExecutionTracer(execution_id="exec-1")
        tracer.start_phase(TracePhase.INTENT_RECEIVED)
        tracer.end_phase(success=True)
        tracer.start_phase(TracePhase.POLICY_EVALUATION)
        tracer.end_phase(success=True)

        trace = tracer.get_trace()
        assert len(trace) == 2
        assert trace[0]["phase"] == "intent.received"
        assert trace[1]["phase"] == "policy.evaluation"

    def test_get_trace_empty_after_clear(self):
        tracer = ExecutionTracer(execution_id="exec-1")
        tracer.start_phase(TracePhase.INTENT_RECEIVED)
        tracer.end_phase(success=True)
        assert len(tracer.get_trace()) == 1

        tracer.clear()
        assert len(tracer.get_trace()) == 0

    def test_get_trace_entry_format(self):
        tracer = ExecutionTracer(execution_id="exec-1", agent_id="a1")
        tracer.start_phase(TracePhase.INTENT_RECEIVED)
        tracer.end_phase(success=True)

        entry = tracer.get_trace()[0]
        assert "phase" in entry
        assert "start_time" in entry
        assert "end_time" in entry
        assert "duration_ms" in entry
        assert "success" in entry


class TestExecutionTracerSummary:
    """Tests for trace summary."""

    def test_summary_success(self):
        tracer = ExecutionTracer(execution_id="exec-1", agent_id="a1", intent_action="deploy")
        tracer.start_phase(TracePhase.INTENT_RECEIVED)
        tracer.end_phase(success=True)
        tracer.start_phase(TracePhase.EXECUTION_COMPLETED)
        tracer.end_phase(success=True)

        summary = tracer.get_summary()
        assert summary["execution_id"] == "exec-1"
        assert summary["agent_id"] == "a1"
        assert summary["intent_action"] == "deploy"
        assert summary["status"] == "success"
        assert summary["phase_count"] == 2
        assert summary["failures"] == 0

    def test_summary_with_failures(self):
        tracer = ExecutionTracer(execution_id="exec-1")
        tracer.start_phase(TracePhase.POLICY_EVALUATION)
        tracer.end_phase(success=True)
        tracer.start_phase(TracePhase.TOOL_EXECUTION)
        tracer.end_phase(success=False, error="Failed")

        summary = tracer.get_summary()
        assert summary["status"] == "failure"
        assert summary["failures"] == 1

    def test_summary_empty(self):
        tracer = ExecutionTracer(execution_id="exec-1")

        summary = tracer.get_summary()
        assert summary["phase_count"] == 0
        assert summary["status"] == "success"


class TestExecutionTracerFullLifecycle:
    """End-to-end: full execution lifecycle through all phases."""

    def test_full_execution_lifecycle(self):
        tracer = ExecutionTracer(
            execution_id="exec-99",
            agent_id="agent-1",
            intent_action="mcp.database.query",
            tenant_id="t1",
        )

        # Simulate the full KitematicRuntime lifecycle
        tracer.start_phase(TracePhase.INTENT_RECEIVED)
        tracer.end_phase(success=True)

        tracer.start_phase(TracePhase.POLICY_EVALUATION)
        tracer.end_phase(success=True)

        tracer.start_phase(TracePhase.CAPABILITY_CHECK)
        tracer.end_phase(success=True)

        tracer.start_phase(TracePhase.INTENT_ROUTING)
        tracer.end_phase(success=True)

        tracer.start_phase(TracePhase.TOOL_EXECUTION, metadata={"tool": "mcp.database.query"})
        tracer.end_phase(success=True)

        tracer.start_phase(TracePhase.CHECKPOINT_SAVE)
        tracer.end_phase(success=True)

        tracer.start_phase(TracePhase.EXECUTION_COMPLETED)
        tracer.end_phase(success=True)

        trace = tracer.get_trace()
        assert len(trace) == 7
        assert trace[0]["phase"] == "intent.received"
        assert trace[6]["phase"] == "execution.completed"
        assert all(t["success"] for t in trace)

        summary = tracer.get_summary()
        assert summary["phase_count"] == 7
        assert summary["status"] == "success"

    def test_lifecycle_with_failure(self):
        tracer = ExecutionTracer(execution_id="exec-98")
        tracer.start_phase(TracePhase.INTENT_RECEIVED)
        tracer.end_phase(success=True)
        tracer.start_phase(TracePhase.POLICY_EVALUATION)
        tracer.end_phase(success=False, error="Policy denied: no matching rule")
        tracer.start_phase(TracePhase.EXECUTION_COMPLETED)
        tracer.end_phase(success=False)

        trace = tracer.get_trace()
        assert len(trace) == 3
        assert trace[1]["success"] is False
        assert trace[1]["error"] == "Policy denied: no matching rule"
