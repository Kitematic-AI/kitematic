"""Tests for API Pydantic schemas/contracts."""

import pytest
from pydantic import ValidationError

from runtime.kitematic_runtime.api.schemas import (
    ErrorResponse,
    ExecutionResponse,
    HealthResponse,
    IntentRequest,
    MetricsResponse,
)


class TestIntentRequest:
    """Request contract for intent submission."""

    def test_valid_minimal(self):
        req = IntentRequest(agent_id="a1", action="mcp.database.query")
        assert req.agent_id == "a1"
        assert req.action == "mcp.database.query"
        assert req.parameters == {}

    def test_valid_with_parameters(self):
        req = IntentRequest(
            agent_id="a1",
            action="mcp.database.query",
            parameters={"query": "SELECT 1"},
        )
        assert req.parameters == {"query": "SELECT 1"}

    def test_missing_agent_id(self):
        with pytest.raises(ValidationError):
            IntentRequest(action="mcp.database.query")

    def test_missing_action(self):
        with pytest.raises(ValidationError):
            IntentRequest(agent_id="a1")

    def test_empty_agent_id(self):
        with pytest.raises(ValidationError):
            IntentRequest(agent_id="", action="mcp.database.query")

    def test_empty_action(self):
        with pytest.raises(ValidationError):
            IntentRequest(agent_id="a1", action="")

    def test_extra_fields_allowed(self):
        req = IntentRequest(agent_id="a1", action="test", extra="ignored")
        assert req.agent_id == "a1"
        assert req.action == "test"


class TestExecutionResponse:
    """Response contract for intent execution."""

    def test_success_response(self):
        resp = ExecutionResponse(
            execution_id="exec-1",
            success=True,
            state="COMPLETED",
            checkpoint_id="cp-abc",
            data={"result": "ok"},
        )
        assert resp.execution_id == "exec-1"
        assert resp.success is True
        assert resp.checkpoint_id == "cp-abc"

    def test_failure_response(self):
        resp = ExecutionResponse(
            execution_id="exec-2",
            success=False,
            state="FAILED",
            error="Policy denied",
        )
        assert resp.success is False
        assert resp.error == "Policy denied"
        assert resp.data == {}

    def test_minimal_response(self):
        resp = ExecutionResponse(
            execution_id="exec-3",
            success=True,
            state="COMPLETED",
        )
        assert resp.checkpoint_id is None
        assert resp.error is None
        assert resp.data == {}


class TestErrorResponse:
    """Error response contract."""

    def test_with_code(self):
        resp = ErrorResponse(error="Not found", code="NOT_FOUND")
        assert resp.error == "Not found"
        assert resp.code == "NOT_FOUND"
        assert resp.details == {}

    def test_default_code(self):
        resp = ErrorResponse(error="Something broke")
        assert resp.code == "RUNTIME_CONTRACT_ERROR"

    def test_with_details(self):
        resp = ErrorResponse(
            error="Validation failed",
            code="VALIDATION_ERROR",
            details={"field": "agent_id"},
        )
        assert resp.details == {"field": "agent_id"}


class TestHealthResponse:
    """Health check contract."""

    def test_default_values(self):
        resp = HealthResponse()
        assert resp.status == "ok"
        assert resp.version == "1.0.0-rc.1"
        assert resp.runtime == "kitematic-runtime"


class TestMetricsResponse:
    """Metrics snapshot contract."""

    def test_empty(self):
        resp = MetricsResponse()
        assert resp.counters == {}
        assert resp.histograms == {}
        assert resp.gauges == {}

    def test_with_data(self):
        resp = MetricsResponse(
            counters={"executions": 10},
            histograms={"latency_ms": {"count": 5, "avg": 100.0}},
            gauges={"active": 3},
        )
        assert resp.counters["executions"] == 10
        assert resp.histograms["latency_ms"]["avg"] == 100.0
        assert resp.gauges["active"] == 3
