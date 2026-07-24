"""Execution budget — resource limits for loop execution.

Prevents infinite loops and resource exhaustion.
Every loop step decrements from the budget.
When budget is exhausted, the loop terminates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass
class ExecutionBudget:
    """Resource budget for loop execution.

    Tracks:
      - Step count (max_steps)
      - Token consumption (max_tokens)
      - Time elapsed (timeout_seconds)

    When any limit is reached, is_exhausted returns True
    and the loop MUST terminate.
    """

    max_steps: int = 10
    max_tokens: int = 100_000
    timeout_seconds: int = 3600

    current_steps: int = 0
    tokens_consumed: int = 0
    started_at: datetime | None = None

    def start(self) -> None:
        """Mark budget as started."""
        if self.started_at is None:
            self.started_at = datetime.now(UTC)

    @property
    def steps_remaining(self) -> int:
        """Remaining steps before exhaustion."""
        return max(0, self.max_steps - self.current_steps)

    @property
    def tokens_remaining(self) -> int:
        """Remaining tokens before exhaustion."""
        return max(0, self.max_tokens - self.tokens_consumed)

    @property
    def is_steps_exhausted(self) -> bool:
        """Check if step limit is reached."""
        return self.current_steps >= self.max_steps

    @property
    def is_tokens_exhausted(self) -> bool:
        """Check if token limit is reached."""
        return self.tokens_consumed >= self.max_tokens

    @property
    def is_timeout(self) -> bool:
        """Check if time limit is reached."""
        if self.started_at is None:
            return False
        elapsed = (datetime.now(UTC) - self.started_at).total_seconds()
        return elapsed > self.timeout_seconds

    @property
    def is_exhausted(self) -> bool:
        """Check if ANY budget limit is reached."""
        return self.is_steps_exhausted or self.is_tokens_exhausted or self.is_timeout

    def consume_step(self, tokens: int = 0) -> None:
        """Consume one step and optional tokens.

        Raises ValueError if budget is already exhausted.
        """
        if self.is_exhausted:
            raise BudgetExhaustedError(
                steps=self.current_steps,
                tokens=self.tokens_consumed,
                max_steps=self.max_steps,
                max_tokens=self.max_tokens,
            )
        self.current_steps += 1
        self.tokens_consumed += tokens

    def reset(self) -> None:
        """Reset budget counters."""
        self.current_steps = 0
        self.tokens_consumed = 0
        self.started_at = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize budget state for audit."""
        return {
            "max_steps": self.max_steps,
            "max_tokens": self.max_tokens,
            "timeout_seconds": self.timeout_seconds,
            "current_steps": self.current_steps,
            "tokens_consumed": self.tokens_consumed,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "is_exhausted": self.is_exhausted,
            "steps_remaining": self.steps_remaining,
            "tokens_remaining": self.tokens_remaining,
        }


class BudgetExhaustedError(Exception):
    """Raised when trying to consume from an exhausted budget."""

    def __init__(self, steps: int, tokens: int, max_steps: int, max_tokens: int):
        self.steps = steps
        self.tokens = tokens
        self.max_steps = max_steps
        self.max_tokens = max_tokens
        super().__init__(
            f"Budget exhausted: steps={steps}/{max_steps}, tokens={tokens}/{max_tokens}"
        )
