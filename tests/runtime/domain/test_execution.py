"""Tests for Execution domain model."""

from datetime import datetime, timedelta

from core.domain.execution import (
    BudgetConsumed,
    Execution,
    ExecutionStatus,
)


class TestExecution:
    def test_valid_execution_passes_validation(self) -> None:
        exec_ = Execution(
            execution_id="exec-123",
            tenant_id="tenant-abc",
            agent_instance_id="agent-inst-1",
            agent_manifest_version="1.0",
            status=ExecutionStatus.RUNNING,
            goal="Analyze Q4 sales data",
        )
        errors = exec_.validate()
        assert len(errors) == 0
        assert exec_.is_valid is True

    def test_missing_required_fields_fails(self) -> None:
        exec_ = Execution(
            execution_id="",
            tenant_id="tenant-abc",
            agent_instance_id="",
            agent_manifest_version="1.0",
            status=ExecutionStatus.PENDING,
            goal="",
        )
        errors = exec_.validate()
        assert len(errors) >= 3
        assert exec_.is_valid is False

    def test_budget_defaults(self) -> None:
        exec_ = Execution(
            execution_id="exec-1",
            tenant_id="t-1",
            agent_instance_id="a-1",
            agent_manifest_version="1.0",
            status=ExecutionStatus.PENDING,
            goal="test",
        )
        assert exec_.total_tokens == 0
        assert exec_.total_cost == 0.0

    def test_budget_with_values(self) -> None:
        exec_ = Execution(
            execution_id="exec-1",
            tenant_id="t-1",
            agent_instance_id="a-1",
            agent_manifest_version="1.0",
            status=ExecutionStatus.RUNNING,
            goal="test",
            budget_consumed=BudgetConsumed(tokens=500, cost_usd=0.02, time_ms=1200),
        )
        assert exec_.total_tokens == 500
        assert exec_.total_cost == 0.02

    def test_duration_computation(self) -> None:
        start = datetime(2026, 1, 1, 10, 0, 0)
        end = start + timedelta(seconds=30)
        exec_ = Execution(
            execution_id="exec-1",
            tenant_id="t-1",
            agent_instance_id="a-1",
            agent_manifest_version="1.0",
            status=ExecutionStatus.COMPLETED,
            goal="test",
            started_at=start,
            completed_at=end,
        )
        assert exec_.duration_ms == 30_000

    def test_zero_duration_when_missing_timestamps(self) -> None:
        exec_ = Execution(
            execution_id="exec-1",
            tenant_id="t-1",
            agent_instance_id="a-1",
            agent_manifest_version="1.0",
            status=ExecutionStatus.PENDING,
            goal="test",
        )
        assert exec_.duration_ms == 0
