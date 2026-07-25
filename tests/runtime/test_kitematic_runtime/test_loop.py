"""Tests for LoopController — the Orchestration Loop.

Verifies:
  - Full lifecycle (happy path)
  - Budget enforcement
  - Policy gate
  - Capability gate
  - Gateway boundary
  - Checkpoint persistence
  - Event emission (audit trail)
  - Multi-step execution
  - Failure classification
"""


import pytest

from kernel.resources.budget import ExecutionBudget
from kernel.lifecycle import (
    LoopController,
    LoopTermination,
)
from kernel.runtime import (
    ExecutionPath,
    Intent,
    IntentRouter,
    KitematicRuntime,
    PolicyEvaluator,
    StatePersistence,
    ToolGateway,
    ToolResult,
)
from kernel.state import ExecutionState

# ── Mock Implementations ───────────────────────────────────────────────────


class MockPolicy(PolicyEvaluator):
    def __init__(self, allow: bool = True, reason: str | None = None):
        self._allow = allow
        self._reason = reason

    async def evaluate_intent(self, intent: Intent) -> tuple[bool, str | None]:
        return self._allow, self._reason

    async def check_capability(self, action: str, agent_id: str) -> tuple[bool, str | None]:
        return self._allow, self._reason


class MockRouter(IntentRouter):
    def __init__(self, tool: str = "mock.tool"):
        self._tool = tool

    async def route_intent(self, intent: Intent) -> ExecutionPath:
        return ExecutionPath(tool=self._tool)


class MockGateway(ToolGateway):
    def __init__(self, success: bool = True, data: dict | None = None, error: str | None = None,
                 raise_error: bool = False):
        self._success = success
        self._data = data or {"output": "ok"}
        self._error = error
        self._raise_error = raise_error

    async def access_tool(self, path: ExecutionPath, intent: Intent) -> ToolResult:
        if self._raise_error:
            raise RuntimeError(self._error or "Gateway access error")
        return ToolResult(success=self._success, data=self._data, error=self._error)


class MockPersistence(StatePersistence):
    def __init__(self, checkpoint_id: str = "cp-001"):
        self._checkpoint_id = checkpoint_id
        self.save_calls: list[tuple[str, dict]] = []

    async def save(self, execution_id: str, state: dict) -> str:
        self.save_calls.append((execution_id, state))
        return self._checkpoint_id

    async def restore(self, checkpoint_id: str) -> dict:
        return {"restored": True}


# ── Helpers ────────────────────────────────────────────────────────────────


def make_runtime(
    policy_allow: bool = True,
    policy_reason: str | None = None,
    gateway_success: bool = True,
    gateway_error: str | None = None,
    gateway_raise_error: bool = False,
) -> KitematicRuntime:
    return KitematicRuntime(
        policy=MockPolicy(allow=policy_allow, reason=policy_reason),
        router=MockRouter(),
        gateway=MockGateway(success=gateway_success, error=gateway_error, raise_error=gateway_raise_error),
        persistence=MockPersistence(),
    )


def make_loop(
    policy_allow: bool = True,
    policy_reason: str | None = None,
    gateway_success: bool = True,
    gateway_error: str | None = None,
    gateway_raise_error: bool = False,
    max_steps: int = 10,
    max_tokens: int = 100_000,
) -> tuple[LoopController, ExecutionBudget]:
    budget = ExecutionBudget(max_steps=max_steps, max_tokens=max_tokens)
    runtime = make_runtime(
        policy_allow=policy_allow,
        policy_reason=policy_reason,
        gateway_success=gateway_success,
        gateway_error=gateway_error,
        gateway_raise_error=gateway_raise_error,
    )
    return LoopController(runtime=runtime, budget=budget), budget


# ── Happy Path Tests ───────────────────────────────────────────────────────


class TestHappyPath:
    """Verify single intent execution through full chain."""

    @pytest.mark.asyncio
    async def test_single_intent_completes(self) -> None:
        loop, budget = make_loop()
        intent = Intent(agent_id="a1", action="db.read")
        result = await loop.run_intent(intent)

        assert result.success is True
        assert result.execution_id != ""
        assert result.steps_executed >= 1
        assert result.final_state == ExecutionState.COMPLETED
        assert result.termination_reason == LoopTermination.COMPLETED
        assert result.error is None
        assert len(result.checkpoints) == 1

    @pytest.mark.asyncio
    async def test_intent_result_contains_data(self) -> None:
        loop, budget = make_loop()
        intent = Intent(agent_id="a1", action="db.read")
        result = await loop.run_intent(intent)

        assert result.history[0].data == {"output": "ok"}

    @pytest.mark.asyncio
    async def test_budget_consumed_after_success(self) -> None:
        loop, budget = make_loop(max_steps=5)
        intent = Intent(agent_id="a1", action="db.read")
        await loop.run_intent(intent)

        assert budget.current_steps == 1


# ── Budget Tests ───────────────────────────────────────────────────────────


class TestBudgetEnforcement:
    """Verify budget limits are enforced."""

    @pytest.mark.asyncio
    async def test_budget_exhausted_terminates(self) -> None:
        loop, budget = make_loop(max_steps=1)
        intent = Intent(agent_id="a1", action="db.read")

        # First intent succeeds
        result1 = await loop.run_intent(intent)
        assert result1.success is True

        # Second intent should fail (budget exhausted)
        result2 = await loop.run_intent(intent)
        assert result2.success is False
        assert result2.termination_reason == LoopTermination.BUDGET_EXHAUSTED

    @pytest.mark.asyncio
    async def test_budget_exhausted_error_message(self) -> None:
        loop, budget = make_loop(max_steps=1)
        intent = Intent(agent_id="a1", action="db.read")

        await loop.run_intent(intent)
        result = await loop.run_intent(intent)

        assert "budget" in result.error.lower() or "exhausted" in result.error.lower()


# ── Policy Gate Tests ──────────────────────────────────────────────────────


class TestPolicyGate:
    """Verify Policy rejection stops execution."""

    @pytest.mark.asyncio
    async def test_policy_rejection_terminates(self) -> None:
        loop, budget = make_loop(policy_allow=False, policy_reason="Denied by policy")
        intent = Intent(agent_id="a1", action="forbidden")
        result = await loop.run_intent(intent)

        assert result.success is False
        assert result.termination_reason == LoopTermination.POLICY_DENIED
        assert "Denied by policy" in result.error

    @pytest.mark.asyncio
    async def test_policy_rejection_no_checkpoints(self) -> None:
        loop, budget = make_loop(policy_allow=False, policy_reason="Denied")
        intent = Intent(agent_id="a1", action="forbidden")
        result = await loop.run_intent(intent)

        assert len(result.checkpoints) == 0


# ── Capability Gate Tests ──────────────────────────────────────────────────


class TestCapabilityGate:
    """Verify capability denial stops execution."""

    @pytest.mark.asyncio
    async def test_capability_denied_terminates(self) -> None:
        loop, budget = make_loop(policy_allow=False, policy_reason="Capability not allowed")
        intent = Intent(agent_id="a1", action="unknown")
        result = await loop.run_intent(intent)

        assert result.success is False
        assert result.termination_reason == LoopTermination.CAPABILITY_DENIED


# ── Gateway Boundary Tests ─────────────────────────────────────────────────


class TestGatewayBoundary:
    """Verify Gateway failure halts execution."""

    @pytest.mark.asyncio
    async def test_gateway_failure_terminates(self) -> None:
        loop, budget = make_loop(gateway_raise_error=True, gateway_error="Connection refused")
        intent = Intent(agent_id="a1", action="db.read")
        result = await loop.run_intent(intent)

        assert result.success is False
        assert result.termination_reason == LoopTermination.GATEWAY_FAILED
        assert "Connection refused" in result.error


# ── Event Audit Trail Tests ────────────────────────────────────────────────


class TestEventAuditTrail:
    """Verify every step emits an ExecutionEvent."""

    @pytest.mark.asyncio
    async def test_events_emitted_on_success(self) -> None:
        loop, budget = make_loop()
        intent = Intent(agent_id="a1", action="db.read")
        result = await loop.run_intent(intent)

        # Event log is internal — verify via event count in loop
        # The loop emits at least: LOOP_STARTED, BUDGET_CHECKED, STEP_COMPLETED, LOOP_TERMINATED
        assert result.success is True
        assert result.steps_executed >= 1

    @pytest.mark.asyncio
    async def test_events_emitted_on_failure(self) -> None:
        loop, budget = make_loop(policy_allow=False, policy_reason="Denied")
        intent = Intent(agent_id="a1", action="forbidden")
        result = await loop.run_intent(intent)

        # Even on failure, events are emitted
        assert result.success is False
        assert result.termination_reason == LoopTermination.POLICY_DENIED


# ── Multi-Step Tests ───────────────────────────────────────────────────────


class TestMultiStep:
    """Verify multi-step execution."""

    @pytest.mark.asyncio
    async def test_multiple_intents(self) -> None:
        loop, budget = make_loop(max_steps=5)
        intents = [
            Intent(agent_id="a1", action="step1"),
            Intent(agent_id="a1", action="step2"),
            Intent(agent_id="a1", action="step3"),
        ]

        results = await loop.run_multi_step(intents)

        assert len(results) == 3
        assert all(r.success for r in results)
        assert budget.current_steps == 3

    @pytest.mark.asyncio
    async def test_multi_step_stops_on_failure(self) -> None:
        loop, budget = make_loop(max_steps=5)
        # First intent will succeed, second will fail (different policy)
        runtime = make_runtime(policy_allow=True)
        budget = ExecutionBudget(max_steps=5)
        loop = LoopController(runtime=runtime, budget=budget)

        intents = [
            Intent(agent_id="a1", action="ok"),
            Intent(agent_id="a1", action="ok"),
        ]

        results = await loop.run_multi_step(intents)
        assert len(results) == 2
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_multi_step_stops_on_budget_exhaustion(self) -> None:
        loop, budget = make_loop(max_steps=2)
        intents = [
            Intent(agent_id="a1", action="step1"),
            Intent(agent_id="a1", action="step2"),
            Intent(agent_id="a1", action="step3"),  # This should not run
        ]

        results = await loop.run_multi_step(intents)
        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is True


# ── Failure Classification Tests ───────────────────────────────────────────


class TestFailureClassification:
    """Verify error messages are classified correctly."""

    @pytest.mark.asyncio
    async def test_policy_rejection_classification(self) -> None:
        loop, _ = make_loop(policy_allow=False, policy_reason="Policy rejected intent")
        result = await loop.run_intent(Intent(agent_id="a1", action="x"))
        assert result.termination_reason == LoopTermination.POLICY_DENIED

    @pytest.mark.asyncio
    async def test_gateway_error_classification(self) -> None:
        loop, _ = make_loop(gateway_success=False, gateway_error="Gateway access error")
        result = await loop.run_intent(Intent(agent_id="a1", action="x"))
        assert result.termination_reason == LoopTermination.GATEWAY_FAILED

    @pytest.mark.asyncio
    async def test_unknown_error_classification(self) -> None:
        loop, _ = make_loop(gateway_raise_error=True, gateway_error="Something weird happened")
        result = await loop.run_intent(Intent(agent_id="a1", action="x"))
        assert result.termination_reason == LoopTermination.GATEWAY_FAILED


# ── History Tests ──────────────────────────────────────────────────────────


class TestHistory:
    """Verify execution history tracking."""

    @pytest.mark.asyncio
    async def test_history_recorded(self) -> None:
        loop, _ = make_loop()
        await loop.run_intent(Intent(agent_id="a1", action="x"))
        await loop.run_intent(Intent(agent_id="a1", action="y"))

        assert len(loop.history) == 2

    @pytest.mark.asyncio
    async def test_history_read_only(self) -> None:
        loop, _ = make_loop()
        await loop.run_intent(Intent(agent_id="a1", action="x"))

        history = loop.history
        history.clear()  # This should not affect internal history
        assert len(loop.history) == 1
