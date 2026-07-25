"""Contract tests for TemplateRepository.

These tests define the contract that ANY TemplateRepository implementation
must satisfy. PostgreSQL adapter must pass the same tests.
"""

import pytest

from control_plane.registry.template_repository import TemplateRepository


@pytest.fixture
def repo() -> TemplateRepository:
    """Override this fixture with the repository under test."""
    from control_plane.registry.memory_template_repository import (
        MemoryTemplateRepository,
    )
    return MemoryTemplateRepository()


class TestTemplateRepositoryContract:
    """Storage-independent contract tests for TemplateRepository."""

    @pytest.mark.asyncio
    async def test_create_returns_template_id(self, repo: TemplateRepository) -> None:
        template_id = await repo.create_template(
            name="test-template",
            framework="langgraph",
            manifest={"runtime_contract_version": "1.0"},
        )
        assert template_id is not None
        assert template_id.startswith("tpl-")

    @pytest.mark.asyncio
    async def test_get_returns_created_template(self, repo: TemplateRepository) -> None:
        template_id = await repo.create_template(
            name="financial-analyst",
            framework="langgraph",
            manifest={"runtime_contract_version": "1.0"},
        )
        template = await repo.get_template(template_id)
        assert template is not None
        assert template["name"] == "financial-analyst"
        assert template["framework"] == "langgraph"

    @pytest.mark.asyncio
    async def test_get_returns_none_for_missing(self, repo: TemplateRepository) -> None:
        template = await repo.get_template("tpl-nonexistent")
        assert template is None

    @pytest.mark.asyncio
    async def test_list_all_templates(self, repo: TemplateRepository) -> None:
        await repo.create_template("t1", "langgraph", {})
        await repo.create_template("t2", "crewai", {})
        templates = await repo.list_templates()
        assert len(templates) == 2

    @pytest.mark.asyncio
    async def test_list_filters_by_framework(self, repo: TemplateRepository) -> None:
        await repo.create_template("t1", "langgraph", {})
        await repo.create_template("t2", "crewai", {})
        await repo.create_template("t3", "langgraph", {})
        templates = await repo.list_templates(framework="langgraph")
        assert len(templates) == 2
        assert all(t["framework"] == "langgraph" for t in templates)

    @pytest.mark.asyncio
    async def test_delete_archives_template(self, repo: TemplateRepository) -> None:
        template_id = await repo.create_template("t1", "langgraph", {})
        await repo.delete_template(template_id)
        template = await repo.get_template(template_id)
        assert template is not None
        assert template["status"] == "archived"

    @pytest.mark.asyncio
    async def test_delete_nonexistent_is_noop(self, repo: TemplateRepository) -> None:
        await repo.delete_template("tpl-nonexistent")
