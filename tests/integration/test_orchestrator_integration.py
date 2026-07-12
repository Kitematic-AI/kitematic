"""Integration tests — Runtime ↔ Control Plane via RuntimeExecutorAdapter."""

import pytest

from runtime.execution.execution_runtime import ExecutionRuntime
from runtime.execution.in_memory_runtime import InMemoryRuntime
from services.control_plane.adapters.runtime_adapter import RuntimeExecutorAdapter
from services.control_plane.agent_registry.agent_registry import AgentRegistry
from services.control_plane.orchestrator.state_machine import ExecutionStateMachine, ExecutionStatus
from services.control_plane.orchestrator.step_coordinator import StepAction


class SimpleAgentRegistry(AgentRegistry):
    def __init__(self) -> None:
        self._instances: dict[str, dict] = {}

    async def create_instance(self, tenant_id: str, template_id: str, name: str, config: dict) -> str:
        instance_id = f"inst-{len(self._instances) + 1}"
        self._instances[instance_id] = {"id": instance_id, "status": "active"}
        return instance_id

    async def get_instance(self, instance_id: str):
        return self._instances.get(instance_id)

    async def update_instance_state(self, instance_id: str, status: str):
        if instance_id in self._instances:
            self._instances[instance_id]["status"] = status

    async def get_manifest(self, instance_id: str):
        return None


class TestFullLifecycleWithAdapter:
    @pytest.mark.asyncio
    async def test_start_then_execute_step_loop(self) -> None:
        registry = SimpleAgentRegistry()
        await registry.create_instance("t-1", "tmpl-1", "agent-1", {})

        sm = ExecutionStateMachine()
        sm.transition(ExecutionStatus.RUNNING, "started", "test")

        rt = InMemoryRuntime()
        adapter = RuntimeExecutorAdapter(runtime=rt)

        plan, resp = await adapter.plan_and_execute(
            execution_id="exec-1",
            agent_id="agent-1",
            goal="compute",
            step_number=1,
            state={},
            budget_remaining=100.0,
            allowed_tools=["mcp.*"],
            sm=sm,
        )

        assert plan.action == StepAction.EXECUTE
        assert resp is not None
        assert resp.status.value == "COMPLETED"
        assert sm.current_state == ExecutionStatus.RUNNING


class TestPolicyDenyBlocksRuntime:
    @pytest.mark.asyncio
    async def test_policy_deny_returns_pause_never_calls_runtime(self) -> None:
        class SpyRuntime(ExecutionRuntime):
            def __init__(self):
                self.called = False

            async def execute_step(self, request, context):
                self.called = True
                from runtime.contracts.step_response import StepResponse, StepStatus
                return StepResponse(status=StepStatus.COMPLETED)

        spy = SpyRuntime()
        adapter = RuntimeExecutorAdapter(runtime=spy)
        sm = ExecutionStateMachine()

        plan, resp = await adapter.plan_and_execute(
            execution_id="exec-1",
            agent_id="agent-1",
            goal="blocked",
            step_number=1,
            state={},
            budget_remaining=0.0,
            allowed_tools=["mcp.*"],
            sm=sm,
        )

        assert plan.action == StepAction.PAUSE_FOR_APPROVAL
        assert resp is None
        assert spy.called is False


class TestRuntimeFailurePropagates:
    @pytest.mark.asyncio
    async def test_failure_transitions_sm_to_failed(self) -> None:
        class FailingRuntime(ExecutionRuntime):
            async def execute_step(self, request, context):
                raise RuntimeError("execution failed")

        adapter = RuntimeExecutorAdapter(runtime=FailingRuntime())
        sm = ExecutionStateMachine()
        sm.transition(ExecutionStatus.RUNNING, "started", "test")

        resp = await adapter.execute_step(
            execution_id="exec-1",
            agent_id="agent-1",
            goal="fail",
            step_number=1,
            state={},
            budget_remaining=100.0,
            allowed_tools=["mcp.*"],
            sm=sm,
        )

        assert resp.status.value == "FAILED"
        assert sm.current_state == ExecutionStatus.FAILED
        assert sm.history[-1].actor == "runtime_adapter"
