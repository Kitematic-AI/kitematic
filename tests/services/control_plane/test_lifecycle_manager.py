"""Contract tests for LifecycleManager."""

import pytest
from services.control_plane.agent_registry.agent_registry import AgentRegistry
from services.control_plane.lifecycle.lifecycle_manager import LifecycleManager
from services.control_plane.errors.orchestration_errors import AgentInstanceNotFoundError


class InMemoryRegistry(AgentRegistry):
    """Test double for AgentRegistry."""

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


@pytest.fixture
def registry() -> InMemoryRegistry:
    reg = InMemoryRegistry()
    reg.add_instance("inst-1", {"id": "inst-1", "name": "test-agent", "status": "active"})
    return reg


@pytest.fixture
def manager(registry: InMemoryRegistry) -> LifecycleManager:
    return LifecycleManager(agent_registry=registry)


class TestLifecycleStartExecution:
    @pytest.mark.asyncio
    async def test_start_returns_execution_id(self, manager: LifecycleManager) -> None:
        execution_id = await manager.start_execution(
            instance_id="inst-1", goal="test"
        )
        assert execution_id.startswith("exec-")

    @pytest.mark.asyncio
    async def test_start_sets_running_state(self, manager: LifecycleManager) -> None:
        execution_id = await manager.start_execution(
            instance_id="inst-1", goal="test"
        )
        status = await manager.get_execution_status(execution_id)
        assert status == "RUNNING"

    @pytest.mark.asyncio
    async def test_start_with_invalid_instance_raises(self, manager: LifecycleManager) -> None:
        with pytest.raises(AgentInstanceNotFoundError):
            await manager.start_execution(instance_id="nonexistent", goal="test")


class TestLifecyclePauseResume:
    @pytest.mark.asyncio
    async def test_pause_sets_paused_state(self, manager: LifecycleManager) -> None:
        execution_id = await manager.start_execution(
            instance_id="inst-1", goal="test"
        )
        await manager.pause_execution(execution_id)
        status = await manager.get_execution_status(execution_id)
        assert status == "PAUSED"

    @pytest.mark.asyncio
    async def test_resume_sets_running_state(self, manager: LifecycleManager) -> None:
        execution_id = await manager.start_execution(
            instance_id="inst-1", goal="test"
        )
        await manager.pause_execution(execution_id)
        await manager.resume_execution(execution_id)
        status = await manager.get_execution_status(execution_id)
        assert status == "RUNNING"


class TestLifecycleStopExecution:
    @pytest.mark.asyncio
    async def test_stop_sets_failed_state(self, manager: LifecycleManager) -> None:
        execution_id = await manager.start_execution(
            instance_id="inst-1", goal="test"
        )
        await manager.stop_execution(execution_id)
        status = await manager.get_execution_status(execution_id)
        assert status == "FAILED"

    @pytest.mark.asyncio
    async def test_stop_on_terminal_state_is_noop(self, manager: LifecycleManager) -> None:
        execution_id = await manager.start_execution(
            instance_id="inst-1", goal="test"
        )
        await manager.stop_execution(execution_id)
        await manager.stop_execution(execution_id)  # second stop
        status = await manager.get_execution_status(execution_id)
        assert status == "FAILED"


class TestTransitionHistory:
    @pytest.mark.asyncio
    async def test_history_records_transitions(self, manager: LifecycleManager) -> None:
        execution_id = await manager.start_execution(
            instance_id="inst-1", goal="test"
        )
        await manager.pause_execution(execution_id)
        await manager.resume_execution(execution_id)

        history = manager.get_transition_history(execution_id)
        assert len(history) == 4  # start, pause, resume→resuming, resuming→running
        assert history[0]["to_state"] == "RUNNING"
        assert history[1]["to_state"] == "PAUSED"
        assert history[2]["to_state"] == "RESUMING"
        assert history[3]["to_state"] == "RUNNING"
