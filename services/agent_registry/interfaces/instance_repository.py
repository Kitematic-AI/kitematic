"""Instance repository interface — Agent instance storage and management."""

from abc import ABC, abstractmethod
from typing import Any


class InstanceRepository(ABC):
    """Interface for Agent instance persistence."""

    @abstractmethod
    async def create_instance(
        self,
        tenant_id: str,
        template_id: str,
        name: str,
        config: dict[str, Any],
    ) -> str:
        """Create a new Agent instance. Returns instance_id."""
        ...

    @abstractmethod
    async def get_instance(self, instance_id: str) -> dict[str, Any] | None:
        """Retrieve an instance by ID."""
        ...

    @abstractmethod
    async def list_instances(
        self, tenant_id: str
    ) -> list[dict[str, Any]]:
        """List all instances for a tenant."""
        ...

    @abstractmethod
    async def update_instance(
        self, instance_id: str, config: dict[str, Any]
    ) -> None:
        """Update instance configuration."""
        ...

    @abstractmethod
    async def delete_instance(self, instance_id: str) -> None:
        """Soft-delete (archive) an instance."""
        ...
