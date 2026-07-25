"""KitematicRuntime — the top-level execution ABI.

Orchestrates the full intent execution chain:
  Intent → Policy → Capability Check → Orchestrator → Gateway → Checkpoint

Runtime executes lifecycle only. Never decides. Never bypasses Gateway.
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from runtime.kitematic_runtime.config.settings import RuntimeSettings
from kernel.exceptions import (
    CheckpointPersistenceError,
    InvalidStateTransitionError,
)
from kernel.isolation import (
    IsolationBoundary,
    MissingTenantContextError,
)
from kernel.observability.context import ObservabilityContext
from kernel.observability.logging import RuntimeLogger
from kernel.observability.metrics import MetricsRegistry
from kernel.observability.tracing import ExecutionTracer, TracePhase
from kernel.state import ExecutionState, RuntimeState, is_valid_transition
from kernel.tenant import TenantContext

# ── ABI Contracts ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Intent:
    """A declaration of desired state from an Agent."""
    agent_id: str
    action: str
    parameters: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class ExecutionResult:
    """Result of executing an Intent through the full chain."""
    success: bool
    execution_id: str = ""
    checkpoint_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    state: ExecutionState = ExecutionState.CREATED


@dataclass(frozen=True)
class ToolResult:
    """Result from MCP Gateway tool access."""
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class ExecutionPath:
    """Routing decision from Orchestrator."""
    tool: str
    adapter: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)


# ── ABI Protocols ──────────────────────────────────────────────────────────


class PolicyEvaluator(ABC):
    """Protocol for Policy Engine — evaluates whether actions are permitted."""

    @abstractmethod
    async def evaluate_intent(self, intent: Intent) -> tuple[bool, str | None]:
        """Evaluate whether an intent is permitted.

        Returns (allowed, reason) where reason is None if allowed,
        or a string explaining rejection.
        """
        ...

    @abstractmethod
    async def check_capability(self, action: str, agent_id: str) -> tuple[bool, str | None]:
        """Check if agent has a capability for the given action.

        Returns (allowed, reason) where reason is None if allowed.
        """
        ...


class IntentRouter(ABC):
    """Protocol for Orchestrator — routes intents to execution paths."""

    @abstractmethod
    async def route_intent(self, intent: Intent) -> ExecutionPath:
        """Route an intent to the correct execution path.

        Raises OrchestrationError if routing fails.
        """
        ...


class ToolGateway(ABC):
    """Protocol for MCP Gateway — the only path to external tools."""

    @abstractmethod
    async def access_tool(self, path: ExecutionPath, intent: Intent) -> ToolResult:
        """Access a tool through the Gateway Chain.

        Raises GatewayAccessError if access fails.
        """
        ...


class StatePersistence(ABC):
    """Protocol for Checkpoint System — immutable state persistence."""

    @abstractmethod
    async def save(self, execution_id: str, state: dict[str, Any]) -> str:
        """Save execution state. Returns checkpoint_id.

        Raises CheckpointPersistenceError if save fails.
        """
        ...

    @abstractmethod
    async def restore(self, checkpoint_id: str) -> dict[str, Any]:
        """Restore execution state from checkpoint.

        Raises CheckpointPersistenceError if restore fails.
        """
        ...


# ── Runtime Implementation ────────────────────────────────────────────────


class KitematicRuntime:
    """The Kitematic Runtime ABI — orchestrates intent execution.

    Responsibilities:
      - Host Agent workloads
      - Execute Intents through Policy → Orchestrator → Gateway → Checkpoint
      - Enforce lifecycle state machine
      - Preserve immutable execution history

    Does NOT:
      - Make allow/reject decisions (Policy Engine's role)
      - Access tools directly (Gateway Chain required)
      - Modify history (append-only)
      - Grant authority to Agents
    """

    def __init__(
        self,
        policy: PolicyEvaluator,
        router: IntentRouter,
        gateway: ToolGateway,
        persistence: StatePersistence,
        isolation: IsolationBoundary | None = None,
        logger: RuntimeLogger | None = None,
        metrics: MetricsRegistry | None = None,
        tracer: type[ExecutionTracer] | None = None,
        settings: RuntimeSettings | None = None,
        quota_manager: Any | None = None,
    ):
        self._policy = policy
        self._router = router
        self._gateway = gateway
        self._persistence = persistence
        self._isolation = isolation
        self._logger = logger
        self._metrics = metrics
        self._tracer_cls = tracer
        self._agents: dict[str, dict[str, Any]] = {}
        self._state: RuntimeState = RuntimeState.RUNNING
        if settings is None:
            from runtime.kitematic_runtime.config.settings import RuntimeSettings as _RS

            settings = _RS()
        self._settings: RuntimeSettings = settings
        self._quota_manager = quota_manager

    def set_tenant_context(self, context: TenantContext) -> None:
        """Set the immutable tenant context for execution.

        TenantContext is captured at execution start and frozen until completion.
        Execution tenant_id CANNOT change mid-flight.
        """
        if not context.is_valid:
            raise MissingTenantContextError()
        if self._isolation is not None:
            self._isolation.validate_tenant_context(context)
        self._tenant_context = context

    @property
    def tenant_context(self) -> TenantContext | None:
        """Get the current tenant context (read-only)."""
        return getattr(self, "_tenant_context", None)

    # ── Agent Management ──────────────────────────────────────────────

    def host_agent(self, agent_id: str, capabilities: list[str]) -> None:
        """Register an Agent with the Runtime.

        Runtime hosts the Agent but does not govern it.
        Capabilities are declarative — Policy Engine decides access.
        """
        self._agents[agent_id] = {
            "capabilities": capabilities,
            "hosted_at": datetime.now(UTC).isoformat(),
        }

    def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        """Retrieve hosted Agent information."""
        return self._agents.get(agent_id)

    def list_agents(self) -> list[str]:
        """List all hosted Agent IDs."""
        return list(self._agents.keys())

    # ── Lifecycle Control ─────────────────────────────────────────

    @property
    def state(self) -> RuntimeState:
        """Current Runtime lifecycle state."""
        return self._state

    async def drain(self) -> None:
        """Transition from RUNNING to DRAINING.

        DRAINING rejects new executions but allows in-flight to complete.
        Idempotent — safe to call multiple times.
        No-op if already DRAINING or STOPPED.
        """
        if self._state != RuntimeState.RUNNING:
            return
        self._state = RuntimeState.DRAINING
        if self._logger:
            self._logger.info("Runtime draining — new executions rejected")

    async def stop(self) -> None:
        """Transition to STOPPED.

        Idempotent — safe to call multiple times.
        Does NOT cancel in-flight executions (runtime is stateless —
        in-flight work is managed by the caller).
        Does NOT release existing resources or clear state.

        Observability:
          - Logs shutdown start and completion
          - Increments runtime.shutdown.count metric
        """
        if self._state == RuntimeState.STOPPED:
            return
        self._state = RuntimeState.STOPPED
        if self._logger:
            self._logger.info("Runtime stopped")
        if self._metrics:
            self._metrics.increment("runtime.shutdown.count")

    # ── Intent Execution ──────────────────────────────────────────────

    async def execute_intent(self, intent: Intent) -> ExecutionResult:
        """Execute an Intent through the full governance chain.

        Execution Flow:
          1. VALIDATE TENANT CONTEXT (if isolation configured)
          2. CREATED → VALIDATING (start)
          3. Policy evaluation
          4. VALIDATING → AUTHORIZED (if policy allows)
          5. Capability check
          6. AUTHORIZED → EXECUTING (if capability exists)
          7. Orchestrator routing
          8. Gateway tool access
          9. EXECUTING → CHECKPOINTING
          10. Checkpoint save
          11. CHECKPOINTING → COMPLETED

        On any failure, transitions to FAILED or HALTED.
        """
        execution_id = str(uuid.uuid4())

        # Step 0: Tenant context validation (only if isolation is configured)
        tenant_ctx = getattr(self, "_tenant_context", None)
        if self._isolation is not None and tenant_ctx is None:
            return ExecutionResult(
                success=False,
                execution_id=execution_id,
                error="No tenant context — execution denied",
                state=ExecutionState.CREATED,
            )
        if tenant_ctx is not None and self._isolation is not None:
            self._isolation.check_resource_limits(tenant_ctx.tenant_id)
            self._isolation.start_execution(tenant_ctx.tenant_id)

        # Quota check — reject if tenant exceeded limits
        quota_tenant = tenant_ctx.tenant_id if tenant_ctx else ""
        quota_acquired = False
        if self._quota_manager is not None and quota_tenant:
            if not self._quota_manager.check_concurrent(quota_tenant):
                if self._metrics:
                    self._metrics.increment("resource.quota.exceeded")
                return ExecutionResult(
                    success=False,
                    execution_id=execution_id,
                    error=f"Concurrent execution limit exceeded for tenant {quota_tenant!r}",
                    state=ExecutionState.CREATED,
                )
            if not self._quota_manager.check_and_consume_rate(quota_tenant):
                retry = self._quota_manager.retry_after(quota_tenant)
                if self._metrics:
                    self._metrics.increment("resource.rate_limit.hit")
                return ExecutionResult(
                    success=False,
                    execution_id=execution_id,
                    error=(
                        f"Rate limit exceeded for tenant {quota_tenant!r}. "
                        f"Retry after {retry:.1f}s"
                    ),
                    state=ExecutionState.CREATED,
                )
            self._quota_manager.start_execution(quota_tenant, execution_id)
            quota_acquired = True

        def _release_quota() -> None:
            if quota_acquired and self._quota_manager is not None and quota_tenant:
                self._quota_manager.end_execution(quota_tenant, execution_id)

        # Shutdown check — reject new executions when draining or stopped
        if self._state == RuntimeState.DRAINING:
            _release_quota()
            if self._logger:
                self._logger.warn("Execution rejected — runtime draining")
            if self._metrics:
                self._metrics.increment("runtime.executions.rejected")
            return ExecutionResult(
                success=False,
                execution_id=execution_id,
                error="Runtime is draining",
                state=ExecutionState.CREATED,
            )
        if self._state == RuntimeState.STOPPED:
            _release_quota()
            if self._logger:
                self._logger.warn("Execution rejected — runtime stopped")
            if self._metrics:
                self._metrics.increment("runtime.executions.rejected")
            return ExecutionResult(
                success=False,
                execution_id=execution_id,
                error="Runtime is stopped",
                state=ExecutionState.CREATED,
            )

        result = await self._execute_quota_guarded(
            execution_id=execution_id,
            intent=intent,
            tenant_ctx=tenant_ctx,
            quota_release=_release_quota,
        )
        _release_quota()
        return result

    async def _execute_quota_guarded(
        self,
        execution_id: str,
        intent: Intent,
        tenant_ctx: Any,
        quota_release: Any,
    ) -> ExecutionResult:
        """Execute intent with quota tracking. Quota is released by caller."""
        obs_ctx = ObservabilityContext(
            execution_id=execution_id,
            tenant_id=tenant_ctx.tenant_id if tenant_ctx else "",
            agent_id=intent.agent_id,
            intent_action=intent.action,
        )
        tracer = self._tracer_cls(**asdict(obs_ctx)) if self._tracer_cls else None
        logger = self._logger.with_correlation(**asdict(obs_ctx)) if self._logger else None
        metrics = self._metrics
        start_time = time.time()

        if logger:
            logger.info("Execution started")
        if metrics:
            metrics.increment("runtime.executions.total")
        if tracer:
            tracer.start_phase(TracePhase.INTENT_RECEIVED)

        state = ExecutionState.CREATED

        state = self._transition(state, ExecutionState.VALIDATING)

        try:
            allowed, reason = await self._policy.evaluate_intent(intent)
        except Exception as e:
            state = self._transition_safe(state, ExecutionState.HALTED)
            if tracer:
                tracer.end_phase(success=False, error=str(e))
            if logger:
                logger.error("Policy evaluation error", error=str(e))
            if metrics:
                metrics.increment("runtime.executions.failed")
            return ExecutionResult(
                success=False,
                execution_id=execution_id,
                error=f"Policy evaluation error: {str(e)}",
                state=state,
            )

        if not allowed:
            state = self._transition_safe(state, ExecutionState.FAILED)
            if tracer:
                tracer.end_phase(success=False, error=reason)
            if logger:
                logger.warn("Policy rejected", reason=reason)
            if metrics:
                metrics.increment("runtime.policy.rejected")
                metrics.increment("runtime.executions.failed")
            return ExecutionResult(
                success=False,
                execution_id=execution_id,
                error=reason or "Policy rejected intent",
                state=state,
            )

        state = self._transition(state, ExecutionState.AUTHORIZED)
        if tracer:
            tracer.end_phase(success=True)
            tracer.start_phase(TracePhase.CAPABILITY_CHECK)

        try:
            cap_allowed, cap_reason = await self._policy.check_capability(
                intent.action, intent.agent_id
            )
        except Exception as e:
            state = self._transition_safe(state, ExecutionState.FAILED)
            if tracer:
                tracer.end_phase(success=False, error=str(e))
            if logger:
                logger.error("Capability check error", error=str(e))
            if metrics:
                metrics.increment("runtime.executions.failed")
            return ExecutionResult(
                success=False,
                execution_id=execution_id,
                error=f"Capability check error: {str(e)}",
                state=state,
            )

        if not cap_allowed:
            state = self._transition_safe(state, ExecutionState.FAILED)
            if tracer:
                tracer.end_phase(success=False, error=cap_reason)
            if logger:
                logger.warn("Capability denied", reason=cap_reason, action=intent.action)
            if metrics:
                metrics.increment("runtime.capability.denied")
                metrics.increment("runtime.executions.failed")
            return ExecutionResult(
                success=False,
                execution_id=execution_id,
                error=cap_reason or f"Capability not allowed for action: {intent.action}",
                state=state,
            )

        state = self._transition(state, ExecutionState.EXECUTING)
        if tracer:
            tracer.end_phase(success=True)
            tracer.start_phase(TracePhase.INTENT_ROUTING)

        try:
            execution_path = await self._router.route_intent(intent)
        except Exception as e:
            state = self._transition_safe(state, ExecutionState.HALTED)
            if tracer:
                tracer.end_phase(success=False, error=str(e))
            if logger:
                logger.error("Orchestration error", error=str(e))
            if metrics:
                metrics.increment("runtime.executions.failed")
            return ExecutionResult(
                success=False,
                execution_id=execution_id,
                error=f"Orchestration error: {str(e)}",
                state=state,
            )

        if tracer:
            tracer.end_phase(success=True)
            tracer.start_phase(TracePhase.TOOL_EXECUTION)

        try:
            tool_result = await self._gateway.access_tool(execution_path, intent)
        except Exception as e:
            state = self._transition_safe(state, ExecutionState.FAILED)
            if tracer:
                tracer.end_phase(success=False, error=str(e))
            if logger:
                logger.error("Gateway access failed", tool=execution_path.tool, error=str(e))
            if metrics:
                metrics.increment("runtime.gateway.error")
                metrics.increment("runtime.executions.failed")
            return ExecutionResult(
                success=False,
                execution_id=execution_id,
                error=f"Gateway access error: {str(e)}",
                state=state,
            )

        if not tool_result.success:
            state = self._transition_safe(state, ExecutionState.FAILED)
            if tracer:
                tracer.end_phase(success=False, error=tool_result.error)
            if logger:
                logger.error("Tool execution failed", error=tool_result.error)
            if metrics:
                metrics.increment("runtime.executions.failed")
            return ExecutionResult(
                success=False,
                execution_id=execution_id,
                error=tool_result.error or "Tool execution failed",
                state=state,
            )

        state = self._transition(state, ExecutionState.CHECKPOINTING)
        if tracer:
            tracer.end_phase(success=True)
            tracer.start_phase(TracePhase.CHECKPOINT_SAVE)

        checkpoint_state: dict[str, Any] = {
            "execution_id": execution_id,
            "intent_action": intent.action,
            "intent_agent": intent.agent_id,
            "tool_result": tool_result.data,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if tenant_ctx is not None:
            checkpoint_state["tenant_id"] = tenant_ctx.tenant_id

        try:
            checkpoint_id = await self._persistence.save(execution_id, checkpoint_state)
        except Exception as e:
            state = self._transition_safe(state, ExecutionState.HALTED)
            if tracer:
                tracer.end_phase(success=False, error=str(e))
            if logger:
                logger.error("Checkpoint save failed", error=str(e))
            if metrics:
                metrics.increment("runtime.checkpoint.error")
                metrics.increment("runtime.executions.failed")
            return ExecutionResult(
                success=False,
                execution_id=execution_id,
                error=f"Checkpoint save error: {str(e)}",
                state=state,
            )

        state = self._transition(state, ExecutionState.COMPLETED)
        if tracer:
            tracer.end_phase(success=True)
            tracer.start_phase(TracePhase.EXECUTION_COMPLETED)
            tracer.end_phase(success=True)

        if self._isolation is not None and tenant_ctx is not None:
            self._isolation.end_execution(tenant_ctx.tenant_id)

        elapsed = (time.time() - start_time) * 1000
        if logger:
            logger.info(
                "Execution completed",
                checkpoint_id=checkpoint_id,
                duration_ms=round(elapsed, 2),
            )
        if metrics:
            metrics.increment("runtime.executions.completed")
            metrics.record("runtime.execution.duration_ms", elapsed)

        return ExecutionResult(
            success=True,
            execution_id=execution_id,
            checkpoint_id=checkpoint_id,
            data=tool_result.data,
            state=state,
        )

    # ── State Machine ─────────────────────────────────────────────────

    def _transition(self, current: ExecutionState, target: ExecutionState) -> ExecutionState:
        """Enforce valid state transition. Raises on invalid transition."""
        if not is_valid_transition(current, target):
            from kernel.state import get_valid_transitions
            valid = [s.value for s in get_valid_transitions(current)]
            raise InvalidStateTransitionError(current.value, target.value, valid)
        return target

    def _transition_safe(self, current: ExecutionState, target: ExecutionState) -> ExecutionState:
        """Attempt transition, falling back to HALTED if invalid."""
        if is_valid_transition(current, target):
            return target
        # If the direct transition is invalid, try via HALTED
        if current != ExecutionState.HALTED and is_valid_transition(current, ExecutionState.HALTED):
            return ExecutionState.HALTED
        # Last resort — return current state (should not happen in normal flow)
        return current

    # ── Checkpoint Restore ────────────────────────────────────────────

    async def restore_from_checkpoint(
        self,
        checkpoint_id: str,
        checkpoint_tenant: str = "",
        checkpoint_agent: str = "",
    ) -> dict[str, Any]:
        """Restore execution state from a checkpoint.

        If tenant context is set, validates checkpoint ownership.
        Raises CheckpointPersistenceError if restore fails.
        """
        tenant_ctx = getattr(self, "_tenant_context", None)
        if (
            tenant_ctx is not None
            and self._isolation is not None
            and checkpoint_tenant
            and checkpoint_agent
        ):
            self._isolation.validate_checkpoint_owner(
                checkpoint_tenant=checkpoint_tenant,
                checkpoint_agent=checkpoint_agent,
                request_tenant=tenant_ctx.tenant_id,
                request_agent=tenant_ctx.agent_id,
            )
        try:
            return await self._persistence.restore(checkpoint_id)
        except CheckpointPersistenceError:
            raise
        except Exception as e:
            raise CheckpointPersistenceError("restore", str(e))
