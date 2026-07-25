"""Tests for KitematicRuntime — the Runtime Contract ABI.

Verifies:
  - State machine enforcement
  - Policy gate (rejection halts execution)
  - Capability gate (missing capability halts execution)
  - Gateway boundary (no direct tool access)
  - Checkpoint persistence (immutable history)
  - Full lifecycle (happy path)
  - Failure paths (each component failure)
"""


import pytest

from kernel.exceptions import (
    InvalidStateTransitionError,
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
from kernel.state import VALID_TRANSITIONS, ExecutionState, is_valid_transition

# ── Mock Implementations ───────────────────────────────────────────────────


class MockPolicyEvaluator(PolicyEvaluator):
    """Mock Policy Engine for testing."""

    def __init__(
        self,
        allow_intent: bool = True,
        allow_capability: bool = True,
        intent_reason: str | None = None,
        cap_reason: str | None = None,
        raise_on_intent: bool = False,
        raise_on_capability: bool = False,
    ):
        self._allow_intent = allow_intent
        self._allow_capability = allow_capability
        self._intent_reason = intent_reason
        self._cap_reason = cap_reason
        self._raise_on_intent = raise_on_intent
        self._raise_on_capability = raise_on_capability
        self.evaluate_calls: list[Intent] = []
        self.capability_calls: list[tuple[str, str]] = []

    async def evaluate_intent(self, intent: Intent) -> tuple[bool, str | None]:
        self.evaluate_calls.append(intent)
        if self._raise_on_intent:
            raise RuntimeError("Policy engine crashed")
        return self._allow_intent, self._intent_reason

    async def check_capability(self, action: str, agent_id: str) -> tuple[bool, str | None]:
        self.capability_calls.append((action, agent_id))
        if self._raise_on_capability:
            raise RuntimeError("Capability check crashed")
        return self._allow_capability, self._cap_reason


class MockIntentRouter(IntentRouter):
    """Mock Orchestrator for testing."""

    def __init__(
        self,
        path: ExecutionPath | None = None,
        raise_error: bool = False,
    ):
        self._path = path or ExecutionPath(tool="mock.tool", adapter="mock-adapter")
        self._raise_error = raise_error
        self.route_calls: list[Intent] = []

    async def route_intent(self, intent: Intent) -> ExecutionPath:
        self.route_calls.append(intent)
        if self._raise_error:
            raise RuntimeError("Router crashed")
        return self._path


class MockToolGateway(ToolGateway):
    """Mock MCP Gateway for testing."""

    def __init__(
        self,
        result: ToolResult | None = None,
        raise_error: bool = False,
    ):
        self._result = result or ToolResult(success=True, data={"output": "ok"})
        self._raise_error = raise_error
        self.access_calls: list[tuple[ExecutionPath, Intent]] = []

    async def access_tool(self, path: ExecutionPath, intent: Intent) -> ToolResult:
        self.access_calls.append((path, intent))
        if self._raise_error:
            raise RuntimeError("Gateway crashed")
        return self._result


class MockStatePersistence(StatePersistence):
    """Mock Checkpoint System for testing."""

    def __init__(
        self,
        checkpoint_id: str = "cp-test-001",
        raise_on_save: bool = False,
        raise_on_restore: bool = False,
    ):
        self._checkpoint_id = checkpoint_id
        self._raise_on_save = raise_on_save
        self._raise_on_restore = raise_on_restore
        self.save_calls: list[tuple[str, dict]] = []
        self.restore_calls: list[str] = []

    async def save(self, execution_id: str, state: dict) -> str:
        self.save_calls.append((execution_id, state))
        if self._raise_on_save:
            raise RuntimeError("Persistence crashed")
        return self._checkpoint_id

    async def restore(self, checkpoint_id: str) -> dict:
        self.restore_calls.append(checkpoint_id)
        if self._raise_on_restore:
            raise RuntimeError("Restore crashed")
        return {"execution_id": "exec-1", "restored": True}


# ── State Machine Tests ────────────────────────────────────────────────────


class TestExecutionStateMachine:
    """Verify state machine transition rules."""

    def test_created_can_only_transition_to_validating(self) -> None:
        valid = VALID_TRANSITIONS[ExecutionState.CREATED]
        assert valid == frozenset({ExecutionState.VALIDATING})

    def test_validating_can_go_to_authorized_or_failed(self) -> None:
        valid = VALID_TRANSITIONS[ExecutionState.VALIDATING]
        assert ExecutionState.AUTHORIZED in valid
        assert ExecutionState.FAILED in valid

    def test_authorized_can_go_to_executing_or_failed(self) -> None:
        valid = VALID_TRANSITIONS[ExecutionState.AUTHORIZED]
        assert ExecutionState.EXECUTING in valid
        assert ExecutionState.FAILED in valid

    def test_executing_can_go_to_checkpointing_failed_or_halted(self) -> None:
        valid = VALID_TRANSITIONS[ExecutionState.EXECUTING]
        assert ExecutionState.CHECKPOINTING in valid
        assert ExecutionState.FAILED in valid
        assert ExecutionState.HALTED in valid

    def test_checkpointing_can_go_to_completed_or_halted(self) -> None:
        valid = VALID_TRANSITIONS[ExecutionState.CHECKPOINTING]
        assert ExecutionState.COMPLETED in valid
        assert ExecutionState.HALTED in valid

    def test_terminal_states_have_no_transitions(self) -> None:
        for state in (ExecutionState.COMPLETED, ExecutionState.FAILED, ExecutionState.HALTED):
            assert VALID_TRANSITIONS[state] == frozenset()

    def test_is_valid_transition_helper(self) -> None:
        assert is_valid_transition(ExecutionState.CREATED, ExecutionState.VALIDATING)
        assert not is_valid_transition(ExecutionState.CREATED, ExecutionState.COMPLETED)
        assert not is_valid_transition(ExecutionState.COMPLETED, ExecutionState.CREATED)

    def test_invalid_transition_raises(self) -> None:
        policy = MockPolicyEvaluator()
        router = MockIntentRouter()
        gateway = MockToolGateway()
        persistence = MockStatePersistence()
        runtime = KitematicRuntime(policy, router, gateway, persistence)

        # Directly calling _transition with invalid states should raise
        with pytest.raises(InvalidStateTransitionError):
            runtime._transition(ExecutionState.COMPLETED, ExecutionState.VALIDATING)


# ── Agent Management Tests ─────────────────────────────────────────────────


class TestAgentManagement:
    """Verify Agent hosting and retrieval."""

    def test_host_agent(self) -> None:
        runtime = KitematicRuntime(
            MockPolicyEvaluator(), MockIntentRouter(), MockToolGateway(), MockStatePersistence()
        )
        runtime.host_agent("agent-1", ["read", "write"])
        assert runtime.get_agent("agent-1") is not None
        assert "read" in runtime.get_agent("agent-1")["capabilities"]

    def test_list_agents(self) -> None:
        runtime = KitematicRuntime(
            MockPolicyEvaluator(), MockIntentRouter(), MockToolGateway(), MockStatePersistence()
        )
        runtime.host_agent("a1", [])
        runtime.host_agent("a2", [])
        assert set(runtime.list_agents()) == {"a1", "a2"}

    def test_get_nonexistent_agent(self) -> None:
        runtime = KitematicRuntime(
            MockPolicyEvaluator(), MockIntentRouter(), MockToolGateway(), MockStatePersistence()
        )
        assert runtime.get_agent("no-such-agent") is None


# ── Happy Path Tests ───────────────────────────────────────────────────────


class TestHappyPath:
    """Verify full lifecycle execution."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self) -> None:
        policy = MockPolicyEvaluator(allow_intent=True, allow_capability=True)
        router = MockIntentRouter(path=ExecutionPath(tool="db.read", adapter="pg-adapter"))
        gateway = MockToolGateway(result=ToolResult(success=True, data={"rows": 42}))
        persistence = MockStatePersistence(checkpoint_id="cp-001")

        runtime = KitematicRuntime(policy, router, gateway, persistence)
        runtime.host_agent("agent-1", ["db.read"])

        intent = Intent(agent_id="agent-1", action="db.read", parameters={"query": "SELECT 1"})
        result = await runtime.execute_intent(intent)

        assert result.success is True
        assert result.execution_id != ""
        assert result.checkpoint_id == "cp-001"
        assert result.data == {"rows": 42}
        assert result.state == ExecutionState.COMPLETED
        assert result.error is None

        # Verify chain was followed
        assert len(policy.evaluate_calls) == 1
        assert policy.evaluate_calls[0].action == "db.read"
        assert len(policy.capability_calls) == 1
        assert len(router.route_calls) == 1
        assert len(gateway.access_calls) == 1
        assert len(persistence.save_calls) == 1

    @pytest.mark.asyncio
    async def test_intent_passthrough(self) -> None:
        """Intent reaches Policy Engine correctly."""
        policy = MockPolicyEvaluator()
        router = MockIntentRouter()
        gateway = MockToolGateway()
        persistence = MockStatePersistence()

        runtime = KitematicRuntime(policy, router, gateway, persistence)
        intent = Intent(agent_id="a1", action="test.action", parameters={"x": 1})
        await runtime.execute_intent(intent)

        assert policy.evaluate_calls[0].agent_id == "a1"
        assert policy.evaluate_calls[0].action == "test.action"
        assert policy.evaluate_calls[0].parameters == {"x": 1}


# ── Policy Gate Tests ──────────────────────────────────────────────────────


class TestPolicyGate:
    """Verify Policy Engine rejection halts execution."""

    @pytest.mark.asyncio
    async def test_policy_rejection_halts(self) -> None:
        policy = MockPolicyEvaluator(allow_intent=False, intent_reason="Denied by policy")
        router = MockIntentRouter()
        gateway = MockToolGateway()
        persistence = MockStatePersistence()

        runtime = KitematicRuntime(policy, router, gateway, persistence)
        intent = Intent(agent_id="a1", action="forbidden.action")
        result = await runtime.execute_intent(intent)

        assert result.success is False
        assert "Denied by policy" in result.error
        assert result.state == ExecutionState.FAILED

        # Router and gateway should NOT have been called
        assert len(router.route_calls) == 0
        assert len(gateway.access_calls) == 0
        assert len(persistence.save_calls) == 0

    @pytest.mark.asyncio
    async def test_policy_exception_halts(self) -> None:
        policy = MockPolicyEvaluator(raise_on_intent=True)
        router = MockIntentRouter()
        gateway = MockToolGateway()
        persistence = MockStatePersistence()

        runtime = KitematicRuntime(policy, router, gateway, persistence)
        result = await runtime.execute_intent(Intent(agent_id="a1", action="x"))

        assert result.success is False
        assert "Policy evaluation error" in result.error
        assert result.state == ExecutionState.HALTED

        assert len(router.route_calls) == 0
        assert len(gateway.access_calls) == 0


# ── Capability Gate Tests ──────────────────────────────────────────────────


class TestCapabilityGate:
    """Verify capability check rejection halts execution."""

    @pytest.mark.asyncio
    async def test_missing_capability_halts(self) -> None:
        policy = MockPolicyEvaluator(allow_intent=True, allow_capability=False, cap_reason="No such capability")
        router = MockIntentRouter()
        gateway = MockToolGateway()
        persistence = MockStatePersistence()

        runtime = KitematicRuntime(policy, router, gateway, persistence)
        result = await runtime.execute_intent(Intent(agent_id="a1", action="unknown.action"))

        assert result.success is False
        assert "No such capability" in result.error
        assert result.state == ExecutionState.FAILED

        assert len(router.route_calls) == 0
        assert len(gateway.access_calls) == 0

    @pytest.mark.asyncio
    async def test_capability_exception_halts(self) -> None:
        policy = MockPolicyEvaluator(allow_intent=True, raise_on_capability=True)
        router = MockIntentRouter()
        gateway = MockToolGateway()
        persistence = MockStatePersistence()

        runtime = KitematicRuntime(policy, router, gateway, persistence)
        result = await runtime.execute_intent(Intent(agent_id="a1", action="x"))

        assert result.success is False
        assert "Capability check error" in result.error
        assert result.state == ExecutionState.FAILED


# ── Gateway Boundary Tests ─────────────────────────────────────────────────


class TestGatewayBoundary:
    """Verify Gateway is the only path to external tools."""

    @pytest.mark.asyncio
    async def test_gateway_failure_halts(self) -> None:
        policy = MockPolicyEvaluator()
        router = MockIntentRouter()
        gateway = MockToolGateway(raise_error=True)
        persistence = MockStatePersistence()

        runtime = KitematicRuntime(policy, router, gateway, persistence)
        result = await runtime.execute_intent(Intent(agent_id="a1", action="x"))

        assert result.success is False
        assert "Gateway access error" in result.error
        assert result.state == ExecutionState.FAILED

        # Checkpoint should NOT have been saved
        assert len(persistence.save_calls) == 0

    @pytest.mark.asyncio
    async def test_tool_failure_halts(self) -> None:
        policy = MockPolicyEvaluator()
        router = MockIntentRouter()
        gateway = MockToolGateway(result=ToolResult(success=False, error="Tool crashed"))
        persistence = MockStatePersistence()

        runtime = KitematicRuntime(policy, router, gateway, persistence)
        result = await runtime.execute_intent(Intent(agent_id="a1", action="x"))

        assert result.success is False
        assert "Tool crashed" in result.error
        assert result.state == ExecutionState.FAILED

    @pytest.mark.asyncio
    async def test_gateway_receives_correct_path(self) -> None:
        """Gateway receives the routing path from Orchestrator."""
        expected_path = ExecutionPath(tool="db.write", adapter="pg")
        router = MockIntentRouter(path=expected_path)
        policy = MockPolicyEvaluator()
        gateway = MockToolGateway()
        persistence = MockStatePersistence()

        runtime = KitematicRuntime(policy, router, gateway, persistence)
        await runtime.execute_intent(Intent(agent_id="a1", action="write"))

        assert gateway.access_calls[0][0] == expected_path


# ── Orchestration Failure Tests ────────────────────────────────────────────


class TestOrchestrationFailure:
    """Verify Orchestrator failure halts execution."""

    @pytest.mark.asyncio
    async def test_router_exception_halts(self) -> None:
        policy = MockPolicyEvaluator()
        router = MockIntentRouter(raise_error=True)
        gateway = MockToolGateway()
        persistence = MockStatePersistence()

        runtime = KitematicRuntime(policy, router, gateway, persistence)
        result = await runtime.execute_intent(Intent(agent_id="a1", action="x"))

        assert result.success is False
        assert "Orchestration error" in result.error
        assert result.state == ExecutionState.HALTED

        assert len(gateway.access_calls) == 0
        assert len(persistence.save_calls) == 0


# ── Checkpoint Tests ───────────────────────────────────────────────────────


class TestCheckpointPersistence:
    """Verify Checkpoint System is the only persistence path."""

    @pytest.mark.asyncio
    async def test_checkpoint_save_failure_halts(self) -> None:
        policy = MockPolicyEvaluator()
        router = MockIntentRouter()
        gateway = MockToolGateway()
        persistence = MockStatePersistence(raise_on_save=True)

        runtime = KitematicRuntime(policy, router, gateway, persistence)
        result = await runtime.execute_intent(Intent(agent_id="a1", action="x"))

        assert result.success is False
        assert "Checkpoint save error" in result.error
        assert result.state == ExecutionState.HALTED

    @pytest.mark.asyncio
    async def test_checkpoint_contains_audit_metadata(self) -> None:
        """Checkpoint state includes execution_id, intent, and timestamp."""
        policy = MockPolicyEvaluator()
        router = MockIntentRouter()
        gateway = MockToolGateway(result=ToolResult(success=True, data={"val": 1}))
        persistence = MockStatePersistence()

        runtime = KitematicRuntime(policy, router, gateway, persistence)
        intent = Intent(agent_id="a1", action="test.action", parameters={"k": "v"})
        await runtime.execute_intent(intent)

        saved_state = persistence.save_calls[0][1]
        assert "execution_id" in saved_state
        assert saved_state["intent_action"] == "test.action"
        assert saved_state["intent_agent"] == "a1"
        assert saved_state["tool_result"] == {"val": 1}
        assert "timestamp" in saved_state

    @pytest.mark.asyncio
    async def test_restore_from_checkpoint(self) -> None:
        persistence = MockStatePersistence()
        runtime = KitematicRuntime(
            MockPolicyEvaluator(), MockIntentRouter(), MockToolGateway(), persistence
        )

        state = await runtime.restore_from_checkpoint("cp-001")
        assert state == {"execution_id": "exec-1", "restored": True}
        assert persistence.restore_calls == ["cp-001"]

    @pytest.mark.asyncio
    async def test_restore_failure_wraps_exception(self) -> None:
        persistence = MockStatePersistence(raise_on_restore=True)
        runtime = KitematicRuntime(
            MockPolicyEvaluator(), MockIntentRouter(), MockToolGateway(), persistence
        )

        with pytest.raises(Exception):
            await runtime.restore_from_checkpoint("cp-bad")


# ── Integration Test ───────────────────────────────────────────────────────


class TestIntegration:
    """End-to-end verification of the full ABI chain."""

    @pytest.mark.asyncio
    async def test_full_chain_ordering(self) -> None:
        """Verify execution follows: Policy → Capability → Router → Gateway → Checkpoint."""
        call_order: list[str] = []

        class OrderTrackingPolicy(PolicyEvaluator):
            async def evaluate_intent(self, intent: Intent) -> tuple[bool, str | None]:
                call_order.append("policy")
                return True, None

            async def check_capability(self, action: str, agent_id: str) -> tuple[bool, str | None]:
                call_order.append("capability")
                return True, None

        class OrderTrackingRouter(IntentRouter):
            async def route_intent(self, intent: Intent) -> ExecutionPath:
                call_order.append("router")
                return ExecutionPath(tool="x")

        class OrderTrackingGateway(ToolGateway):
            async def access_tool(self, path: ExecutionPath, intent: Intent) -> ToolResult:
                call_order.append("gateway")
                return ToolResult(success=True, data={})

        class OrderTrackingPersistence(StatePersistence):
            async def save(self, execution_id: str, state: dict) -> str:
                call_order.append("checkpoint")
                return "cp-1"

            async def restore(self, checkpoint_id: str) -> dict:
                return {}

        runtime = KitematicRuntime(
            OrderTrackingPolicy(),
            OrderTrackingRouter(),
            OrderTrackingGateway(),
            OrderTrackingPersistence(),
        )

        await runtime.execute_intent(Intent(agent_id="a1", action="x"))

        assert call_order == ["policy", "capability", "router", "gateway", "checkpoint"]

    @pytest.mark.asyncio
    async def test_policy_rejection_short_circuits(self) -> None:
        """Policy rejection should not reach Router, Gateway, or Checkpoint."""
        call_order: list[str] = []

        class ShortCircuitPolicy(PolicyEvaluator):
            async def evaluate_intent(self, intent: Intent) -> tuple[bool, str | None]:
                call_order.append("policy")
                return False, "Denied"

            async def check_capability(self, action: str, agent_id: str) -> tuple[bool, str | None]:
                call_order.append("capability")
                return True, None

        class TrackingRouter(IntentRouter):
            async def route_intent(self, intent: Intent) -> ExecutionPath:
                call_order.append("router")
                return ExecutionPath(tool="x")

        class TrackingGateway(ToolGateway):
            async def access_tool(self, path: ExecutionPath, intent: Intent) -> ToolResult:
                call_order.append("gateway")
                return ToolResult(success=True)

        class TrackingPersistence(StatePersistence):
            async def save(self, execution_id: str, state: dict) -> str:
                call_order.append("checkpoint")
                return "cp-1"

            async def restore(self, checkpoint_id: str) -> dict:
                return {}

        runtime = KitematicRuntime(
            ShortCircuitPolicy(), TrackingRouter(), TrackingGateway(), TrackingPersistence()
        )
        result = await runtime.execute_intent(Intent(agent_id="a1", action="x"))

        assert result.success is False
        assert call_order == ["policy"]
        assert "router" not in call_order
        assert "gateway" not in call_order
        assert "checkpoint" not in call_order
