"""Tests for ExecutionBudget — resource limits for loop execution."""

from datetime import UTC, datetime, timedelta

import pytest

from runtime.kitematic_runtime.budget import BudgetExhaustedError, ExecutionBudget


class TestBudgetCreation:
    """Verify budget initialization and defaults."""

    def test_default_budget(self) -> None:
        budget = ExecutionBudget()
        assert budget.max_steps == 10
        assert budget.max_tokens == 100_000
        assert budget.timeout_seconds == 3600
        assert budget.current_steps == 0
        assert budget.tokens_consumed == 0
        assert budget.started_at is None

    def test_custom_budget(self) -> None:
        budget = ExecutionBudget(max_steps=5, max_tokens=10_000, timeout_seconds=60)
        assert budget.max_steps == 5
        assert budget.max_tokens == 10_000
        assert budget.timeout_seconds == 60

    def test_budget_starts_with_zero_usage(self) -> None:
        budget = ExecutionBudget()
        assert budget.current_steps == 0
        assert budget.tokens_consumed == 0
        assert budget.is_exhausted is False


class TestBudgetStart:
    """Verify budget start behavior."""

    def test_start_sets_timestamp(self) -> None:
        budget = ExecutionBudget()
        budget.start()
        assert budget.started_at is not None

    def test_start_only_once(self) -> None:
        budget = ExecutionBudget()
        budget.start()
        first = budget.started_at
        budget.start()
        assert budget.started_at == first


class TestBudgetConsumption:
    """Verify budget consumption and exhaustion."""

    def test_consume_step(self) -> None:
        budget = ExecutionBudget(max_steps=5)
        budget.consume_step()
        assert budget.current_steps == 1
        assert budget.steps_remaining == 4

    def test_consume_step_with_tokens(self) -> None:
        budget = ExecutionBudget(max_tokens=1000)
        budget.consume_step(tokens=100)
        assert budget.tokens_consumed == 100
        assert budget.tokens_remaining == 900

    def test_steps_exhausted(self) -> None:
        budget = ExecutionBudget(max_steps=2)
        budget.consume_step()
        budget.consume_step()
        assert budget.is_steps_exhausted is True
        assert budget.is_exhausted is True

    def test_tokens_exhausted(self) -> None:
        budget = ExecutionBudget(max_tokens=100)
        budget.consume_step(tokens=100)
        assert budget.is_tokens_exhausted is True
        assert budget.is_exhausted is True

    def test_consume_after_exhaustion_raises(self) -> None:
        budget = ExecutionBudget(max_steps=1)
        budget.consume_step()
        with pytest.raises(BudgetExhaustedError):
            budget.consume_step()

    def test_steps_remaining(self) -> None:
        budget = ExecutionBudget(max_steps=5)
        assert budget.steps_remaining == 5
        budget.consume_step()
        assert budget.steps_remaining == 4
        budget.consume_step()
        assert budget.steps_remaining == 3

    def test_tokens_remaining(self) -> None:
        budget = ExecutionBudget(max_tokens=1000)
        assert budget.tokens_remaining == 1000
        budget.consume_step(tokens=300)
        assert budget.tokens_remaining == 700


class TestBudgetTimeout:
    """Verify timeout detection."""

    def test_no_timeout_without_start(self) -> None:
        budget = ExecutionBudget(timeout_seconds=1)
        assert budget.is_timeout is False

    def test_no_timeout_within_limit(self) -> None:
        budget = ExecutionBudget(timeout_seconds=3600)
        budget.start()
        assert budget.is_timeout is False

    def test_timeout_after_limit(self) -> None:
        budget = ExecutionBudget(timeout_seconds=1)
        budget.start()
        budget.started_at = datetime.now(UTC) - timedelta(seconds=2)
        assert budget.is_timeout is True

    def test_timeout_triggers_exhaustion(self) -> None:
        budget = ExecutionBudget(timeout_seconds=1)
        budget.start()
        budget.started_at = datetime.now(UTC) - timedelta(seconds=2)
        assert budget.is_exhausted is True


class TestBudgetReset:
    """Verify budget reset behavior."""

    def test_reset_clears_counters(self) -> None:
        budget = ExecutionBudget(max_steps=5, max_tokens=1000)
        budget.start()
        budget.consume_step(tokens=200)
        budget.consume_step(tokens=300)

        budget.reset()

        assert budget.current_steps == 0
        assert budget.tokens_consumed == 0
        assert budget.started_at is None
        assert budget.is_exhausted is False


class TestBudgetSerialization:
    """Verify budget serialization for audit."""

    def test_to_dict(self) -> None:
        budget = ExecutionBudget(max_steps=5, max_tokens=1000, timeout_seconds=60)
        budget.start()
        budget.consume_step(tokens=100)

        d = budget.to_dict()
        assert d["max_steps"] == 5
        assert d["max_tokens"] == 1000
        assert d["timeout_seconds"] == 60
        assert d["current_steps"] == 1
        assert d["tokens_consumed"] == 100
        assert d["started_at"] is not None
        assert d["is_exhausted"] is False
        assert d["steps_remaining"] == 4
        assert d["tokens_remaining"] == 900
