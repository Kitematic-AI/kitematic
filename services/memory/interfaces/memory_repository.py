"""Memory repository interface — long-lived knowledge storage contract."""

from abc import ABC, abstractmethod

from runtime.domain.memory import MemoryItem, MemoryType


class MemoryRepository(ABC):
    """Interface for Agent memory persistence.

    Responsibilities:
      - Store long-lived knowledge (facts, preferences, summaries, experiences)
      - Filter expired items on read (get/search/list_by_agent)
      - Deterministic ordering (created_at ascending, item_id tie-breaker)
      - Deep-copy isolation on all paths (save input, get/search/list output)

    Does NOT:
      - Perform semantic/vector search (out of scope for in-memory impl)
      - Perform network calls or LLM invocations
    """

    @abstractmethod
    async def save(self, memory: MemoryItem) -> MemoryItem:
        """Store a memory item. Returns the stored deep copy."""
        ...

    @abstractmethod
    async def get(self, memory_id: str) -> MemoryItem | None:
        """Retrieve by ID. Returns None if not found or expired."""
        ...

    @abstractmethod
    async def search(
        self,
        query: str,
        agent_instance_id: str | None = None,
        memory_type: MemoryType | None = None,
        min_confidence: float = 0.0,
    ) -> list[MemoryItem]:
        """Content substring search. Expired items excluded.

        Results ordered by created_at ascending, then item_id ascending.
        """
        ...

    @abstractmethod
    async def list_by_agent(
        self, agent_instance_id: str
    ) -> list[MemoryItem]:
        """All non-expired memories for an agent. Ordered by created_at ascending."""
        ...

    @abstractmethod
    async def delete(self, memory_id: str) -> None:
        """Delete by ID. No-op if not found."""
        ...
