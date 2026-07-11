"""In-memory TemplateRepository implementation.

Stores Agent templates in a dict. Implements the TemplateRepository interface.
This is the reference implementation; PostgreSQL adapter will follow later.
"""

from typing import Any
from services.agent_registry.interfaces.template_repository import TemplateRepository
from runtime.domain.agent_manifest import AgentManifest, AgentIdentity, RuntimeDefinition, Capabilities, Constraints


class MemoryTemplateRepository(TemplateRepository):
    """In-memory storage for Agent templates."""

    def __init__(self) -> None:
        self._templates: dict[str, dict[str, Any]] = {}
        self._next_id: int = 1

    async def create_template(
        self, name: str, framework: str, manifest: dict[str, Any]
    ) -> str:
        template_id = f"tpl-{self._next_id}"
        self._next_id += 1

        self._templates[template_id] = {
            "id": template_id,
            "name": name,
            "framework": framework,
            "manifest": manifest,
            "status": "active",
        }
        return template_id

    async def get_template(self, template_id: str) -> dict[str, Any] | None:
        return self._templates.get(template_id)

    async def list_templates(
        self, framework: str | None = None
    ) -> list[dict[str, Any]]:
        templates = list(self._templates.values())
        if framework:
            templates = [t for t in templates if t["framework"] == framework]
        return templates

    async def delete_template(self, template_id: str) -> None:
        if template_id in self._templates:
            self._templates[template_id]["status"] = "archived"
