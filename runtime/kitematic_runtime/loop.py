"""LoopController — the Orchestration Loop for intent execution.

Orchestrates the full governance chain:
  Intent → Budget → Policy → Capability → Router → Gateway → Checkpoint → Result

LoopController manages execution flow, but Runtime + Policy remain
the authority boundaries. LoopController NEVER decides — it routes.

Every step emits an ExecutionEvent for complete audit trail.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from runtime.kitematic_runtime.budget import ExecutionBudget
from runtime.kitematic_runtime.events import EventLog, EventType
from runtime.kitematic_runtime.observability.logging import RuntimeLogger
from runtime.kitematic_runtime.observability.metrics import MetricsRegistry
from runtime.kitematic_runtime.runtime import (
    ExecutionResult,
    Intent,
    KitematicRuntime,
)
from runtime.kitematic_runtime.states import ExecutionState, RuntimeState
from runtime.kitematic_runtime.tenant import TenantContext

# ── Loop Termination Reasons ───────────────────────────────────────────────


class LoopTermination(Enum):
    """Reasons for loop termination."""

    COMPLETED = "COMPLETED"
    POLICY_DENIED = "POLICY_DENIED"
    CAPABILITY_MISSING = "CAPABILITY_MISSING"
    CAPABILITY_DENIED = "CAPABILITY_DENIED"
    GATEWAY_FAILED = "GATEWAY_FAILED"
    TOOL_FAILED = "TOOL_FAILED"
    CHECKPOINT_FAILED = "CHECKPOINT_FAILED"
    ORCHESTRATION_FAILED = "ORCHESTRATION_FAILED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    TIMEOUT = "TIMEOUT"
    EXCEPTION = "EXCEPTION"


# ── Loop Result ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LoopResult:
    """Result of running the orchestration loop."""

    success: bool
    execution_id: str
    steps_executed: int
    tokens_consumed: int
    checkpoints: list[str]
    final_state: ExecutionState
    termination_reason: LoopTermination
    error: str | None = None
    history: list[ExecutionResult] = field(default_factory=list)


# ── Loop Exceptions ────────────────────────────────────────────────────────


class LoopBudgetExhaustedError(Exception):
    """Raised when the loop exhausts its budget."""

    def __init__(self, steps: int, tokens: int):
        self.steps = steps
        self.tokens = tokens
        super().__init__(
            f"Loop budget exhausted: steps={steps}, tokens={tokens}"
        )


class LoopTimeoutError(Exception):
    """Raised when the loop exceeds its time limit."""

    def __init__(self, elapsed_seconds: float, timeout_seconds: float):
        self.elapsed_seconds = elapsed_seconds
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Loop timeout: {elapsed_seconds:.1f}s > {timeout_seconds}s"
        )


# ── LoopController ─────────────────────────────────────────────────────────


class LoopController:
    """Orchestration Loop — manages the full execution lifecycle.

    Responsibilities:
      - Execute Intent through Policy → Capability → Router → Gateway → Checkpoint
      - Enforce budget limits (steps, tokens, timeout)
      - Emit ExecutionEvents for complete audit trail
      - Track execution history
      - Propagate TenantContext to Runtime

    Does NOT:
      - Make allow/reject decisions (Runtime + Policy Engine)
      - Access tools directly (Gateway Chain)
      - Modify history (append-only)
      - Grant authority to Agents
    """

    def __init__(
        self,
        runtime: KitematicRuntime,
        budget: ExecutionBudget,
        tenant_context: TenantContext | None = None,
        logger: RuntimeLogger | None = None,
        metrics: MetricsRegistry | None = None,
    ):
        self._runtime = runtime
        self._budget = budget
        self._history: list[ExecutionResult] = []
        self._logger = logger
        self._metrics = metrics
        self._state: RuntimeState = RuntimeState.RUNNING
        if tenant_context is not None:
            self._runtime.set_tenant_context(tenant_context)

    def set_tenant_context(self, context: TenantContext) -> None:
        """Set the immutable tenant context for execution."""
        self._runtime.set_tenant_context(context)

    @property
    def state(self) -> RuntimeState:
        """Current Runtime lifecycle state."""
        return self._state

    async def shutdown(self, timeout_seconds: float = 30.0) -> None:
        """Shutdown the loop controller, preventing new intents.

        Idempotent — safe to call multiple times.
        Runtime.stop() propagates shutdown intent downward through all
        controllers; LoopController.shutdown() is the runtime-aware
        counterpart for standalone loop usage.
        """
        if self._state != RuntimeState.RUNNING:
            return
        self._state = RuntimeState.STOPPED
        if self._logger:
            self._logger.info("Loop shutting down", timeout_seconds=timeout_seconds)

    async def run_intent(
        self,
        intent: Intent,
        execution_id: str | None = None,
    ) -> LoopResult:
        """Execute a single Intent through the full governance chain.

        This is the primary entry point for the Orchestration Loop.

        Execution Flow:
          1. Start budget
          2. Check budget limits
          3. Emit LOOP_STARTED event
          4. Execute via Runtime
          5. Track result
          6. Emit completion event
          7. Return LoopResult

        On failure:
          - Emits appropriate failure event
          - Returns LoopResult with error details
        """
        execution_id = execution_id or str(uuid.uuid4())
        event_log = EventLog(execution_id)

        if self._state != RuntimeState.RUNNING:
            return LoopResult(
                success=False,
                execution_id=execution_id,
                steps_executed=self._budget.current_steps,
                tokens_consumed=self._budget.tokens_consumed,
                checkpoints=[],
                final_state=ExecutionState.HALTED,
                termination_reason=LoopTermination.EXCEPTION,
                error="Loop is shutting down",
                history=[],
            )

        # Start budget tracking
        self._budget.start()

        # Observability setup
        loop_logger = (
            self._logger.with_correlation(execution_id=execution_id)
            if self._logger
            else None
        )
        metrics = self._metrics

        if loop_logger:
            loop_logger.info("Loop started", agent_id=intent.agent_id, action=intent.action)
        if metrics:
            metrics.increment("runtime.loop.started")

        # Emit LOOP_STARTED
        event_log.emit(
            EventType.LOOP_STARTED,
            state=ExecutionState.CREATED.value,
            metadata={
                "agent_id": intent.agent_id,
                "action": intent.action,
            },
        )

        try:
            # Step 0: Budget validation
            self._check_budget(event_log, execution_id)
            # Execute through Runtime (full chain)
            result = await self._runtime.execute_intent(intent)

            # Track history
            self._history.append(result)

            # Emit step completion event
            if result.success:
                event_log.emit(
                    EventType.STEP_COMPLETED,
                    state=result.state.value,
                    metadata={
                        "execution_id": result.execution_id,
                        "checkpoint_id": result.checkpoint_id,
                    },
                )
                event_log.emit(
                    EventType.LOOP_TERMINATED,
                    state=ExecutionState.COMPLETED.value,
                    metadata={"termination_reason": LoopTermination.COMPLETED.value},
                )
                if loop_logger:
                    loop_logger.info("Loop completed", steps=self._budget.current_steps)
                if metrics:
                    metrics.increment("runtime.loop.completed")
            else:
                termination = self._classify_failure(result.error or "")
                event_log.emit(
                    EventType.LOOP_FAILED,
                    state=result.state.value,
                    metadata={"termination_reason": termination.value},
                    error=result.error,
                )
                if loop_logger:
                    loop_logger.warn(
                        "Loop failed",
                        reason=result.error,
                        termination=termination.value,
                    )
                if metrics:
                    metrics.increment("runtime.loop.failed")

            # Consume budget step
            self._budget.consume_step(tokens=0)

            return LoopResult(
                success=result.success,
                execution_id=execution_id,
                steps_executed=self._budget.current_steps,
                tokens_consumed=self._budget.tokens_consumed,
                checkpoints=[result.checkpoint_id] if result.checkpoint_id else [],
                final_state=result.state,
                termination_reason=(
                    LoopTermination.COMPLETED if result.success
                    else self._classify_failure(result.error or "")
                ),
                error=result.error,
                history=[result],
            )

        except LoopBudgetExhaustedError as e:
            event_log.emit(
                EventType.BUDGET_EXHAUSTED,
                state=ExecutionState.HALTED.value,
                error=str(e),
            )
            if loop_logger:
                loop_logger.warn("Budget exhausted", steps=self._budget.current_steps)
            if metrics:
                metrics.increment("runtime.loop.budget_exhausted")
            return LoopResult(
                success=False,
                execution_id=execution_id,
                steps_executed=self._budget.current_steps,
                tokens_consumed=self._budget.tokens_consumed,
                checkpoints=[],
                final_state=ExecutionState.HALTED,
                termination_reason=LoopTermination.BUDGET_EXHAUSTED,
                error=str(e),
                history=[],
            )

        except LoopTimeoutError as e:
            event_log.emit(
                EventType.TIMEOUT_OCCURRED,
                state=ExecutionState.HALTED.value,
                error=str(e),
            )
            if loop_logger:
                loop_logger.warn("Loop timeout", error=str(e))
            if metrics:
                metrics.increment("runtime.loop.timeout")
            return LoopResult(
                success=False,
                execution_id=execution_id,
                steps_executed=self._budget.current_steps,
                tokens_consumed=self._budget.tokens_consumed,
                checkpoints=[],
                final_state=ExecutionState.HALTED,
                termination_reason=LoopTermination.TIMEOUT,
                error=str(e),
                history=[],
            )

        except Exception as e:
            event_log.emit(
                EventType.LOOP_HALTED,
                state=ExecutionState.HALTED.value,
                error=str(e),
            )
            if loop_logger:
                loop_logger.error("Loop halted unexpectedly", error=str(e))
            if metrics:
                metrics.increment("runtime.loop.exception")
            return LoopResult(
                success=False,
                execution_id=execution_id,
                steps_executed=self._budget.current_steps,
                tokens_consumed=self._budget.tokens_consumed,
                checkpoints=[],
                final_state=ExecutionState.HALTED,
                termination_reason=LoopTermination.EXCEPTION,
                error=str(e),
                history=[],
            )

    async def run_multi_step(
        self,
        intents: list[Intent],
    ) -> list[LoopResult]:
        """Execute multiple Intents sequentially.

        Each Intent goes through the full governance chain.
        Loop terminates early if any step fails or budget is exhausted.
        """
        results: list[LoopResult] = []

        for intent in intents:
            # Check budget before each step
            if self._budget.is_exhausted:
                break

            result = await self.run_intent(intent)
            results.append(result)

            # Stop on failure
            if not result.success:
                break

        return results

    def _check_budget(self, event_log: EventLog, execution_id: str) -> None:
        """Check budget limits before execution."""
        if self._budget.is_exhausted:
            raise LoopBudgetExhaustedError(
                steps=self._budget.current_steps,
                tokens=self._budget.tokens_consumed,
            )

        if self._budget.is_timeout:
            elapsed = 0.0
            if self._budget.started_at:
                elapsed = (datetime.now(UTC) - self._budget.started_at).total_seconds()
            raise LoopTimeoutError(elapsed, self._budget.timeout_seconds)

        event_log.emit(
            EventType.BUDGET_CHECKED,
            state=ExecutionState.CREATED.value,
            metadata=self._budget.to_dict(),
        )

    def _classify_failure(self, error: str) -> LoopTermination:
        """Classify an error into a termination reason."""
        error_lower = error.lower()
        # Policy failures
        if "policy" in error_lower:
            return LoopTermination.POLICY_DENIED
        if error_lower in ("denied", "rejected"):
            return LoopTermination.POLICY_DENIED
        # Capability failures
        if "capability" in error_lower:
            if "not" in error_lower or "denied" in error_lower:
                return LoopTermination.CAPABILITY_DENIED
            return LoopTermination.CAPABILITY_MISSING
        # Gateway failures
        if "gateway" in error_lower:
            return LoopTermination.GATEWAY_FAILED
        # Orchestration failures
        if "orchestration" in error_lower:
            return LoopTermination.ORCHESTRATION_FAILED
        # Checkpoint failures
        if "checkpoint" in error_lower:
            return LoopTermination.CHECKPOINT_FAILED
        # Tool failures
        if "tool" in error_lower:
            return LoopTermination.TOOL_FAILED
        return LoopTermination.EXCEPTION

    @property
    def history(self) -> list[ExecutionResult]:
        """Get execution history (read-only)."""
        return list(self._history)

    @property
    def total_steps(self) -> int:
        """Total steps executed."""
        return self._budget.current_steps

    @property
    def total_tokens(self) -> int:
        """Total tokens consumed."""
        return self._budget.tokens_consumed

    def get_event_log(self, execution_id: str) -> EventLog:
        """Get event log for an execution."""
        return EventLog(execution_id)
