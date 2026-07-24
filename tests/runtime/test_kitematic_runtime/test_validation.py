"""Invariant Validation Suite — verifies all architectural invariants hold.

Every test maps to a specific invariant from the Constitution or ABI.
No runtime code changes — validation only.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from runtime.kitematic_runtime.events import EventLog, EventType
from runtime.kitematic_runtime.exceptions import InvalidStateTransitionError
from runtime.kitematic_runtime.gateway import MCPToolGateway
from runtime.kitematic_runtime.isolation import (
    CrossAgentAccessError,
    CrossTenantAccessError,
    IsolationBoundary,
)
from runtime.kitematic_runtime.runtime import (
    ExecutionPath,
    Intent,
    IntentRouter,
    KitematicRuntime,
    PolicyEvaluator,
    StatePersistence,
    ToolGateway,
    ToolResult,
)
from runtime.kitematic_runtime.states import VALID_TRANSITIONS, ExecutionState, is_valid_transition
from runtime.kitematic_runtime.tenant import TenantContext, TenantModel
from runtime.kitematic_runtime.tool_registry import ToolDefinition, ToolRegistry

# ── Mock Implementations ───────────────────────────────────────────────


class MockPolicy(PolicyEvaluator):
    def __init__(self, allow=True, raise_on=False):
        self._allow = allow
        self._raise = raise_on

    async def evaluate_intent(self, intent):
        if self._raise:
            raise RuntimeError("policy crash")
        return self._allow, None if self._allow else "denied"

    async def check_capability(self, action, agent_id):
        if self._raise:
            raise RuntimeError("cap crash")
        return self._allow, None if self._allow else "no cap"


class MockRouter(IntentRouter):
    def __init__(self, raise_on=False):
        self._raise = raise_on

    async def route_intent(self, intent):
        if self._raise:
            raise RuntimeError("router crash")
        return ExecutionPath(tool="t1", parameters={})


class MockGateway(ToolGateway):
    def __init__(self, success=True, raise_on=False):
        self._success = success
        self._raise = raise_on
        self.call_count = 0

    async def access_tool(self, path, intent):
        self.call_count += 1
        if self._raise:
            raise RuntimeError("gateway crash")
        return ToolResult(success=self._success, data={"ok": True})


class MockPersistence(StatePersistence):
    def __init__(self, fail_save=False, fail_restore=False):
        self._fail_save = fail_save
        self._fail_restore = fail_restore
        self.saved = []

    async def save(self, execution_id, state):
        if self._fail_save:
            raise RuntimeError("checkpoint save failed")
        self.saved.append(state)
        return "cp-1"

    async def restore(self, checkpoint_id):
        if self._fail_restore:
            raise RuntimeError("checkpoint restore failed")
        return {"restored": True}


# ── State Machine Invariants ────────────────────────────────────────────


class TestStateMachineInvariants:
    """Every state machine rule must hold."""

    def test_created_only_to_validating(self):
        assert is_valid_transition(ExecutionState.CREATED, ExecutionState.VALIDATING)

    def test_created_cannot_skip_to_executing(self):
        assert not is_valid_transition(ExecutionState.CREATED, ExecutionState.EXECUTING)

    def test_created_cannot_go_to_completed(self):
        assert not is_valid_transition(ExecutionState.CREATED, ExecutionState.COMPLETED)

    def test_validating_three_targets(self):
        valid = VALID_TRANSITIONS[ExecutionState.VALIDATING]
        assert valid == frozenset({
            ExecutionState.AUTHORIZED,
            ExecutionState.FAILED,
            ExecutionState.HALTED,
        })

    def test_authorized_three_targets(self):
        valid = VALID_TRANSITIONS[ExecutionState.AUTHORIZED]
        assert valid == frozenset({
            ExecutionState.EXECUTING,
            ExecutionState.FAILED,
            ExecutionState.HALTED,
        })

    def test_executing_three_targets(self):
        valid = VALID_TRANSITIONS[ExecutionState.EXECUTING]
        assert valid == frozenset({
            ExecutionState.CHECKPOINTING,
            ExecutionState.FAILED,
            ExecutionState.HALTED,
        })

    def test_checkpointing_two_targets(self):
        valid = VALID_TRANSITIONS[ExecutionState.CHECKPOINTING]
        assert valid == frozenset({
            ExecutionState.COMPLETED,
            ExecutionState.HALTED,
        })

    def test_completed_terminal(self):
        assert VALID_TRANSITIONS[ExecutionState.COMPLETED] == frozenset()

    def test_failed_terminal(self):
        assert VALID_TRANSITIONS[ExecutionState.FAILED] == frozenset()

    def test_halted_terminal(self):
        assert VALID_TRANSITIONS[ExecutionState.HALTED] == frozenset()

    def test_invalid_transition_raises(self):
        with pytest.raises(InvalidStateTransitionError):
            runtime = KitematicRuntime(
                policy=MockPolicy(),
                router=MockRouter(),
                gateway=MockGateway(),
                persistence=MockPersistence(),
            )
            runtime._transition(ExecutionState.COMPLETED, ExecutionState.VALIDATING)

    def test_all_states_enumerated(self):
        assert len(ExecutionState) == 8


# ── Policy Gate Invariants ──────────────────────────────────────────────


class TestPolicyGateInvariant:
    """Policy MUST be evaluated before execution."""

    @pytest.mark.asyncio
    async def test_policy_rejection_halts(self):
        runtime = KitematicRuntime(
            policy=MockPolicy(allow=False),
            router=MockRouter(),
            gateway=MockGateway(),
            persistence=MockPersistence(),
        )
        result = await runtime.execute_intent(Intent(agent_id="a1", action="x"))
        assert result.success is False
        assert result.state == ExecutionState.FAILED

    @pytest.mark.asyncio
    async def test_policy_exception_halts(self):
        runtime = KitematicRuntime(
            policy=MockPolicy(raise_on=True),
            router=MockRouter(),
            gateway=MockGateway(),
            persistence=MockPersistence(),
        )
        result = await runtime.execute_intent(Intent(agent_id="a1", action="x"))
        assert result.success is False
        assert result.state == ExecutionState.HALTED

    @pytest.mark.asyncio
    async def test_no_execution_without_policy(self):
        gw = MockGateway()
        runtime = KitematicRuntime(
            policy=MockPolicy(allow=False),
            router=MockRouter(),
            gateway=gw,
            persistence=MockPersistence(),
        )
        await runtime.execute_intent(Intent(agent_id="a1", action="x"))
        assert gw.call_count == 0

    @pytest.mark.asyncio
    async def test_policy_approval_continues(self):
        runtime = KitematicRuntime(
            policy=MockPolicy(allow=True),
            router=MockRouter(),
            gateway=MockGateway(),
            persistence=MockPersistence(),
        )
        result = await runtime.execute_intent(Intent(agent_id="a1", action="x"))
        assert result.success is True


# ── Capability Gate Invariants ──────────────────────────────────────────


class TestCapabilityGateInvariant:
    """Capability MUST exist before gateway access."""

    @pytest.mark.asyncio
    async def test_missing_capability_halts(self):
        runtime = KitematicRuntime(
            policy=MockPolicy(),
            router=MockRouter(),
            gateway=MockGateway(),
            persistence=MockPersistence(),
        )
        # Override policy to deny capability
        runtime._policy = MagicMock(spec=PolicyEvaluator)
        runtime._policy.evaluate_intent = AsyncMock(return_value=(True, None))
        runtime._policy.check_capability = AsyncMock(return_value=(False, "no cap"))

        result = await runtime.execute_intent(Intent(agent_id="a1", action="x"))
        assert result.success is False
        assert result.state == ExecutionState.FAILED

    @pytest.mark.asyncio
    async def test_capability_exception_halts(self):
        runtime = KitematicRuntime(
            policy=MockPolicy(),
            router=MockRouter(),
            gateway=MockGateway(),
            persistence=MockPersistence(),
        )
        runtime._policy = MagicMock(spec=PolicyEvaluator)
        runtime._policy.evaluate_intent = AsyncMock(return_value=(True, None))
        runtime._policy.check_capability = AsyncMock(side_effect=RuntimeError("cap crash"))

        result = await runtime.execute_intent(Intent(agent_id="a1", action="x"))
        assert result.success is False
        assert result.state == ExecutionState.FAILED

    @pytest.mark.asyncio
    async def test_no_gateway_without_capability(self):
        gw = MockGateway()
        runtime = KitematicRuntime(
            policy=MockPolicy(),
            router=MockRouter(),
            gateway=gw,
            persistence=MockPersistence(),
        )
        runtime._policy = MagicMock(spec=PolicyEvaluator)
        runtime._policy.evaluate_intent = AsyncMock(return_value=(True, None))
        runtime._policy.check_capability = AsyncMock(return_value=(False, "denied"))

        await runtime.execute_intent(Intent(agent_id="a1", action="x"))
        assert gw.call_count == 0


# ── Gateway Boundary Invariants ────────────────────────────────────────


class TestGatewayBoundaryInvariant:
    """No direct tool access without Gateway."""

    @pytest.mark.asyncio
    async def test_unregistered_tool_raises(self):
        registry = ToolRegistry()
        gateway = MCPToolGateway(registry=registry)
        intent = Intent(agent_id="a1", action="x")
        path = ExecutionPath(tool="nonexistent")
        with pytest.raises(Exception):
            await gateway.access_tool(path, intent)

    @pytest.mark.asyncio
    async def test_missing_client_raises(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(tool_id="t1", mcp_server="s1"))
        gateway = MCPToolGateway(registry=registry)
        intent = Intent(agent_id="a1", action="x")
        path = ExecutionPath(tool="t1")
        with pytest.raises(Exception):
            await gateway.access_tool(path, intent)

    @pytest.mark.asyncio
    async def test_mcp_failure_wraps_error(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(tool_id="t1", mcp_server="s1"))

        class FailingClient:
            async def call_tool(self, name, args):
                raise RuntimeError("boom")

        gateway = MCPToolGateway(registry=registry, clients={"s1": FailingClient()})
        intent = Intent(agent_id="a1", action="x")
        path = ExecutionPath(tool="t1")
        with pytest.raises(Exception):
            await gateway.access_tool(path, intent)

    @pytest.mark.asyncio
    async def test_gateway_is_only_path(self):
        gw = MockGateway()
        runtime = KitematicRuntime(
            policy=MockPolicy(),
            router=MockRouter(),
            gateway=gw,
            persistence=MockPersistence(),
        )
        await runtime.execute_intent(Intent(agent_id="a1", action="x"))
        assert gw.call_count == 1

    @pytest.mark.asyncio
    async def test_successful_gateway_returns_tool_result(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(tool_id="t1", mcp_server="s1"))

        class MockClient:
            async def call_tool(self, name, args):
                return {"result": "ok"}

        gateway = MCPToolGateway(registry=registry, clients={"s1": MockClient()})
        intent = Intent(agent_id="a1", action="x")
        path = ExecutionPath(tool="t1")
        result = await gateway.access_tool(path, intent)
        assert isinstance(result, ToolResult)
        assert result.success is True


# ── Tenant Isolation Invariants ────────────────────────────────────────


class TestTenantIsolationInvariant:
    """Tenants cannot access each other's resources."""

    def test_cross_tenant_state_denied(self):
        boundary = IsolationBoundary()
        with pytest.raises(CrossTenantAccessError):
            boundary.validate_state_owner("t1", "a1", "t2", "a1")

    def test_cross_agent_state_denied(self):
        boundary = IsolationBoundary()
        with pytest.raises(CrossAgentAccessError):
            boundary.validate_state_owner("t1", "a1", "t1", "a2")

    def test_cross_tenant_checkpoint_denied(self):
        boundary = IsolationBoundary()
        with pytest.raises(CrossTenantAccessError):
            boundary.validate_checkpoint_owner("t1", "a1", "t2", "a1")

    def test_cross_agent_checkpoint_denied(self):
        boundary = IsolationBoundary()
        with pytest.raises(CrossAgentAccessError):
            boundary.validate_checkpoint_owner("t1", "a1", "t1", "a2")

    @pytest.mark.asyncio
    async def test_no_tenant_context_denied_with_isolation(self):
        boundary = IsolationBoundary()
        boundary.register_tenant(TenantModel(tenant_id="t1", name="T"))
        runtime = KitematicRuntime(
            policy=MockPolicy(),
            router=MockRouter(),
            gateway=MockGateway(),
            persistence=MockPersistence(),
            isolation=boundary,
        )
        result = await runtime.execute_intent(Intent(agent_id="a1", action="x"))
        assert result.success is False
        assert "tenant" in result.error.lower()

    @pytest.mark.asyncio
    async def test_valid_tenant_context_allows(self):
        boundary = IsolationBoundary()
        boundary.register_tenant(TenantModel(tenant_id="t1", name="T"))
        boundary.register_agent("a1", "t1")
        runtime = KitematicRuntime(
            policy=MockPolicy(),
            router=MockRouter(),
            gateway=MockGateway(),
            persistence=MockPersistence(),
            isolation=boundary,
        )
        runtime.set_tenant_context(TenantContext(tenant_id="t1", agent_id="a1"))
        result = await runtime.execute_intent(Intent(agent_id="a1", action="x"))
        assert result.success is True


# ── Immutability Invariants ────────────────────────────────────────────


class TestImmutabilityInvariant:
    """History and checkpoints cannot be modified."""

    def test_event_log_is_append_only(self):
        log = EventLog("exec-1")
        log.emit(EventType.LOOP_STARTED)
        log.emit(EventType.STEP_COMPLETED)
        assert log.count == 2
        # Cannot modify events
        with pytest.raises(AttributeError):
            log.events[0].event_type = EventType.LOOP_FAILED

    def test_tool_definition_frozen(self):
        td = ToolDefinition(tool_id="t1", mcp_server="s1")
        with pytest.raises(AttributeError):
            td.tool_id = "t2"

    def test_tenant_model_frozen(self):
        tm = TenantModel(tenant_id="t1", name="T")
        with pytest.raises(AttributeError):
            tm.tenant_id = "t2"

    def test_tenant_context_frozen(self):
        tc = TenantContext(tenant_id="t1", agent_id="a1")
        with pytest.raises(AttributeError):
            tc.tenant_id = "t2"

    def test_execution_event_frozen(self):
        log = EventLog("exec-1")
        event = log.emit(EventType.LOOP_STARTED)
        with pytest.raises(AttributeError):
            event.event_type = EventType.LOOP_FAILED

    def test_tool_result_frozen(self):
        tr = ToolResult(success=True, data={"a": 1})
        with pytest.raises(AttributeError):
            tr.success = False


# ── Audit Trail Invariants ─────────────────────────────────────────────


class TestAuditTrailInvariant:
    """Every action must produce an audit record."""

    @pytest.mark.asyncio
    async def test_gateway_emits_event(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(tool_id="t1", mcp_server="s1"))

        class MockClient:
            async def call_tool(self, name, args):
                return {"result": "ok"}

        gateway = MCPToolGateway(registry=registry, clients={"s1": MockClient()})
        event_log = EventLog("exec-1")
        gateway.set_event_log(event_log)

        intent = Intent(agent_id="a1", action="x")
        await gateway.access_tool(ExecutionPath(tool="t1"), intent)

        events = event_log.get_events_by_type(EventType.GATEWAY_ACCESSED)
        assert len(events) == 1

    def test_event_log_records_all(self):
        log = EventLog("exec-1")
        for _ in range(10):
            log.emit(EventType.STEP_COMPLETED)
        assert log.count == 10

    def test_audit_log_ordered(self):
        log = EventLog("exec-1")
        e1 = log.emit(EventType.LOOP_STARTED)
        e2 = log.emit(EventType.STEP_COMPLETED)
        e3 = log.emit(EventType.LOOP_TERMINATED)
        assert e1.step_number < e2.step_number < e3.step_number
