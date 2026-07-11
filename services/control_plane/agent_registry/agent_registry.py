"""AgentRegistry — high-level abstraction for agent lifecycle operations.

Orchestrator depends on this interface, NOT on concrete repository implementations.
This keeps the dependency direction correct:

  Orchestrator → AgentRegistry → TemplateRepository / InstanceRepository
"""

from abc import ABC, abstractmethod
from typing import Any


class AgentRegistry(ABC):
    """Abstraction for agent state operations used by the Orchestrator."""

    @abstractmethod
    async def get_instance(self, instance_id: str) -> dict[str, Any] | None:
        """Retrieve agent instance by ID."""
        ...

    @abstractmethod
    async def update_instance_state(
        self, instance_id: str, status: str
    ) -> None:
        """Update agent instance execution status."""
        ...

    @abstractmethod
    async def get_manifest(
        self, instance_id: str
    ) -> dict[str, Any] | None:
        """Retrieve agent manifest (capabilities, constraints, tools)."""
        ...
