"""Template repository interface — Agent template storage and retrieval."""

from abc import ABC, abstractmethod
from typing import Any


class TemplateRepository(ABC):
    """Interface for Agent template persistence."""

    @abstractmethod
    async def create_template(
        self, name: str, framework: str, manifest: dict[str, Any]
    ) -> str:
        """Create a new Agent template. Returns template_id."""
        ...

    @abstractmethod
    async def get_template(self, template_id: str) -> dict[str, Any] | None:
        """Retrieve a template by ID."""
        ...

    @abstractmethod
    async def list_templates(
        self, framework: str | None = None
    ) -> list[dict[str, Any]]:
        """List available templates, optionally filtered by framework."""
        ...

    @abstractmethod
    async def delete_template(self, template_id: str) -> None:
        """Soft-delete (archive) a template."""
        ...
