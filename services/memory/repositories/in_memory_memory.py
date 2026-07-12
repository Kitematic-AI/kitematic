"""In-memory MemoryRepository implementation.

Stores MemoryItems as deep-copied snapshots in a dict.
UUID-based IDs, deterministic ordering, automatic expiration filtering.
"""

import copy
from datetime import datetime, timezone
from uuid import uuid4

from runtime.domain.memory import MemoryItem, MemoryType
from services.memory.interfaces.memory_repository import MemoryRepository


class InMemoryMemoryRepository(MemoryRepository):
    """In-memory memory store with deep-copy immutability and expiration filtering."""

    def __init__(self) -> None:
        self._store: dict[str, MemoryItem] = {}
        self._agent_index: dict[str, set[str]] = {}

    def _is_not_expired(self, memory: MemoryItem) -> bool:
        return not memory.is_expired

    def _sorted(self, items: list[MemoryItem]) -> list[MemoryItem]:
        return sorted(
            items,
            key=lambda m: (m.created_at or datetime.min, m.item_id),
        )

    async def save(self, memory: MemoryItem) -> MemoryItem:
        stored = copy.deepcopy(memory)
        self._store[stored.item_id] = stored
        self._agent_index.setdefault(stored.agent_instance_id, set()).add(
            stored.item_id
        )
        return copy.deepcopy(stored)

    async def get(self, memory_id: str) -> MemoryItem | None:
        item = self._store.get(memory_id)
        if item is None or item.is_expired:
            return None
        return copy.deepcopy(item)

    async def search(
        self,
        query: str,
        agent_instance_id: str | None = None,
        memory_type: MemoryType | None = None,
        min_confidence: float = 0.0,
    ) -> list[MemoryItem]:
        query_lower = query.lower()
        results: list[MemoryItem] = []
        for item in self._store.values():
            if not self._is_not_expired(item):
                continue
            if agent_instance_id is not None and item.agent_instance_id != agent_instance_id:
                continue
            if memory_type is not None and item.type != memory_type:
                continue
            if item.confidence < min_confidence:
                continue
            if query_lower not in item.content.lower():
                continue
            results.append(item)
        return [copy.deepcopy(m) for m in self._sorted(results)]

    async def list_by_agent(
        self, agent_instance_id: str
    ) -> list[MemoryItem]:
        ids = self._agent_index.get(agent_instance_id, set())
        items = [self._store[iid] for iid in ids]
        filtered = [i for i in items if self._is_not_expired(i)]
        return [copy.deepcopy(m) for m in self._sorted(filtered)]

    async def delete(self, memory_id: str) -> None:
        if memory_id in self._store:
            item = self._store.pop(memory_id)
            agent_ids = self._agent_index.get(item.agent_instance_id, set())
            agent_ids.discard(memory_id)
