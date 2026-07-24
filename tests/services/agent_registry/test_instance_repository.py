"""Contract tests for InstanceRepository.

These tests define the contract that ANY InstanceRepository implementation
must satisfy. PostgreSQL adapter must pass the same tests.
"""

import pytest

from services.agent_registry.interfaces.instance_repository import InstanceRepository


@pytest.fixture
def repo() -> InstanceRepository:
    """Override this fixture with the repository under test."""
    from services.agent_registry.repositories.memory_instance_repository import (
        MemoryInstanceRepository,
    )
    return MemoryInstanceRepository()


class TestInstanceRepositoryContract:
    """Storage-independent contract tests for InstanceRepository."""

    @pytest.mark.asyncio
    async def test_create_returns_instance_id(self, repo: InstanceRepository) -> None:
        instance_id = await repo.create_instance(
            tenant_id="tenant-1",
            template_id="tpl-1",
            name="my-agent",
            config={"allowed_tools": ["salesforce.read"]},
        )
        assert instance_id is not None
        assert instance_id.startswith("inst-")

    @pytest.mark.asyncio
    async def test_get_returns_created_instance(self, repo: InstanceRepository) -> None:
        instance_id = await repo.create_instance(
            tenant_id="tenant-1",
            template_id="tpl-1",
            name="my-agent",
            config={},
        )
        instance = await repo.get_instance(instance_id)
        assert instance is not None
        assert instance["name"] == "my-agent"
        assert instance["tenant_id"] == "tenant-1"

    @pytest.mark.asyncio
    async def test_get_returns_none_for_missing(self, repo: InstanceRepository) -> None:
        instance = await repo.get_instance("inst-nonexistent")
        assert instance is None

    @pytest.mark.asyncio
    async def test_list_filters_by_tenant(self, repo: InstanceRepository) -> None:
        await repo.create_instance("t1", "tpl-1", "agent-1", {})
        await repo.create_instance("t1", "tpl-1", "agent-2", {})
        await repo.create_instance("t2", "tpl-1", "agent-3", {})
        instances = await repo.list_instances(tenant_id="t1")
        assert len(instances) == 2

    @pytest.mark.asyncio
    async def test_update_merges_config(self, repo: InstanceRepository) -> None:
        instance_id = await repo.create_instance(
            "t1", "tpl-1", "agent-1", {"allowed_tools": ["salesforce.read"]}
        )
        await repo.update_instance(instance_id, {"allowed_tools": ["salesforce.read", "github.read"]})
        instance = await repo.get_instance(instance_id)
        assert instance["config"]["allowed_tools"] == ["salesforce.read", "github.read"]

    @pytest.mark.asyncio
    async def test_delete_archives_instance(self, repo: InstanceRepository) -> None:
        instance_id = await repo.create_instance("t1", "tpl-1", "agent-1", {})
        await repo.delete_instance(instance_id)
        instance = await repo.get_instance(instance_id)
        assert instance is not None
        assert instance["status"] == "archived"

    @pytest.mark.asyncio
    async def test_delete_nonexistent_is_noop(self, repo: InstanceRepository) -> None:
        await repo.delete_instance("inst-nonexistent")
