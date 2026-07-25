"""End-to-end scenarios — isolated high-level tests for complete flows."""

import pytest

from control_plane.registry.agents import AgentRegistry
from control_plane.lifecycle.manager import LifecycleManager
from control_plane.orchestrator.coordinator import StepAction, StepCoordinator
from control_plane.policy.engine import PolicyEngine


class InMemoryRegistry(AgentRegistry):
    """Isolated test double for each E2E scenario."""

    def __init__(self) -> None:
        self._instances: dict[str, dict] = {}

    def add_instance(self, instance_id: str, data: dict) -> None:
        self._instances[instance_id] = data

    async def get_instance(self, instance_id: str):
        return self._instances.get(instance_id)

    async def update_instance_state(self, instance_id: str, status: str):
        if instance_id in self._instances:
            self._instances[instance_id]["status"] = status

    async def get_manifest(self, instance_id: str):
        return self._instances.get(instance_id)


# ──────────────────────────────────────────────
# Happy Path
# ──────────────────────────────────────────────
class TestHappyPath:
    """template → instance → start → plan → ALLOW → complete"""

    @pytest.mark.asyncio
    async def test_full_happy_flow(self) -> None:
        # Arrange
        registry = InMemoryRegistry()
        registry.add_instance("agent-happy", {"id": "agent-happy", "name": "happy-agent"})
        lifecycle = LifecycleManager(agent_registry=registry)
        policy = PolicyEngine()
        coordinator = StepCoordinator(max_steps=10)

        await policy.create_policy("allow-all", "mcp.*", "ALLOW")

        # Act + Assert
        execution_id = await lifecycle.start_execution("agent-happy", "achieve goal")
        assert await lifecycle.get_execution_status(execution_id) == "RUNNING"

        plan = coordinator.plan_step(execution_id, 1, "achieve goal", 100.0, ["mcp.*"])
        assert plan.action == StepAction.EXECUTE

        decision = await policy.evaluate("agent-happy", "read", "mcp.database.read")
        assert decision["decision"] == "ALLOW"

        sm = lifecycle._get_state_machine(execution_id)
        from control_plane.orchestrator.state_machine import ExecutionStatus
        sm.transition(ExecutionStatus.COMPLETED, "goal_achieved", "orchestrator")
        assert await lifecycle.get_execution_status(execution_id) == "COMPLETED"


# ──────────────────────────────────────────────
# Approval Path
# ──────────────────────────────────────────────
class TestApprovalPath:
    """start → REQUIRE_APPROVAL → pause → resume → complete"""

    @pytest.mark.asyncio
    async def test_approval_flow(self) -> None:
        registry = InMemoryRegistry()
        registry.add_instance("agent-approval", {"id": "agent-approval", "name": "approval-agent"})
        lifecycle = LifecycleManager(agent_registry=registry)
        policy = PolicyEngine()
        coordinator = StepCoordinator(max_steps=10)

        await policy.create_policy("require-approval", "mcp.*", "REQUIRE_APPROVAL")

        execution_id = await lifecycle.start_execution("agent-approval", "sensitive task")
        assert await lifecycle.get_execution_status(execution_id) == "RUNNING"

        decision = await policy.evaluate("agent-approval", "delete", "mcp.database.delete")
        assert decision["decision"] == "REQUIRE_APPROVAL"

        await lifecycle.pause_execution(execution_id)
        assert await lifecycle.get_execution_status(execution_id) == "PAUSED"

        await lifecycle.resume_execution(execution_id)
        assert await lifecycle.get_execution_status(execution_id) == "RUNNING"

        sm = lifecycle._get_state_machine(execution_id)
        from control_plane.orchestrator.state_machine import ExecutionStatus
        sm.transition(ExecutionStatus.COMPLETED, "approved_and_done", "orchestrator")
        assert await lifecycle.get_execution_status(execution_id) == "COMPLETED"


# ──────────────────────────────────────────────
# Deny Path
# ──────────────────────────────────────────────
class TestDenyPath:
    """start → DENY → FAILED"""

    @pytest.mark.asyncio
    async def test_deny_flow(self) -> None:
        registry = InMemoryRegistry()
        registry.add_instance("agent-deny", {"id": "agent-deny", "name": "deny-agent"})
        lifecycle = LifecycleManager(agent_registry=registry)
        policy = PolicyEngine()

        await policy.create_policy("block-all", "model.*", "DENY")

        execution_id = await lifecycle.start_execution("agent-deny", "blocked task")
        assert await lifecycle.get_execution_status(execution_id) == "RUNNING"

        decision = await policy.evaluate("agent-deny", "call", "model.gpt-4")
        assert decision["decision"] == "DENY"

        await lifecycle.stop_execution(execution_id)
        assert await lifecycle.get_execution_status(execution_id) == "FAILED"
