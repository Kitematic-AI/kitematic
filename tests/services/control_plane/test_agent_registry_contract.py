"""Contract tests for AgentRegistry.

These tests define the contract that ANY AgentRegistry implementation
must satisfy.
"""

import pytest

from control_plane.registry.agents import AgentRegistry


@pytest.fixture
def registry() -> AgentRegistry:
    """Override this fixture with the registry under test."""
    from control_plane.registry.memory_instance_repository import (
        MemoryInstanceRepository,
    )
    from control_plane.registry.memory_template_repository import (
        MemoryTemplateRepository,
    )

    class InMemoryAgentRegistry(AgentRegistry):
        def __init__(self) -> None:
            self._templates = MemoryTemplateRepository()
            self._instances = MemoryInstanceRepository()

        async def get_instance(self, instance_id: str):
            return await self._instances.get_instance(instance_id)

        async def update_instance_state(self, instance_id: str, status: str):
            await self._instances.update_instance(instance_id, {"status": status})

        async def get_manifest(self, instance_id: str):
            return await self._instances.get_instance(instance_id)

    return InMemoryAgentRegistry()


class TestAgentRegistryContract:
    """Storage-independent contract tests for AgentRegistry."""

    @pytest.mark.asyncio
    async def test_get_instance_returns_none_for_missing(
        self, registry: AgentRegistry
    ) -> None:
        result = await registry.get_instance("inst-nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_manifest_returns_none_for_missing(
        self, registry: AgentRegistry
    ) -> None:
        result = await registry.get_manifest("inst-nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_instance_state_does_not_raise(
        self, registry: AgentRegistry
    ) -> None:
        # Should not raise even for nonexistent instance
        await registry.update_instance_state("inst-nonexistent", "running")
