"""In-memory InstanceRepository implementation.

Stores Agent instances in a dict. Implements the InstanceRepository interface.
This is the reference implementation; PostgreSQL adapter will follow later.
"""

from typing import Any

from services.agent_registry.interfaces.instance_repository import InstanceRepository


class MemoryInstanceRepository(InstanceRepository):
    """In-memory storage for Agent instances."""

    def __init__(self) -> None:
        self._instances: dict[str, dict[str, Any]] = {}
        self._next_id: int = 1

    async def create_instance(
        self,
        tenant_id: str,
        template_id: str,
        name: str,
        config: dict[str, Any],
    ) -> str:
        instance_id = f"inst-{self._next_id}"
        self._next_id += 1

        self._instances[instance_id] = {
            "id": instance_id,
            "tenant_id": tenant_id,
            "template_id": template_id,
            "name": name,
            "config": config,
            "status": "active",
        }
        return instance_id

    async def get_instance(self, instance_id: str) -> dict[str, Any] | None:
        return self._instances.get(instance_id)

    async def list_instances(
        self, tenant_id: str
    ) -> list[dict[str, Any]]:
        return [
            inst
            for inst in self._instances.values()
            if inst["tenant_id"] == tenant_id
        ]

    async def update_instance(
        self, instance_id: str, config: dict[str, Any]
    ) -> None:
        if instance_id in self._instances:
            self._instances[instance_id]["config"].update(config)

    async def delete_instance(self, instance_id: str) -> None:
        if instance_id in self._instances:
            self._instances[instance_id]["status"] = "archived"
