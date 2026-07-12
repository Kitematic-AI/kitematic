"""Integration tests — Memory with Runtime execution."""

from datetime import datetime, timezone

import pytest

from runtime.domain.memory import MemoryItem, MemoryType
from services.memory.repositories.in_memory_memory import InMemoryMemoryRepository


class TestMemoryRuntimeIntegration:
    @pytest.mark.asyncio
    async def test_save_then_list_by_agent(self) -> None:
        repo = InMemoryMemoryRepository()
        mem = MemoryItem(
            item_id="mem-int-1",
            tenant_id="t-1",
            agent_instance_id="agent-int",
            type=MemoryType.FACT,
            content="Integration test memory",
            confidence=0.85,
            source="integration",
            created_at=datetime(2026, 7, 12, tzinfo=timezone.utc),
        )
        await repo.save(mem)

        result = await repo.list_by_agent("agent-int")
        assert len(result) == 1
        assert result[0].content == "Integration test memory"

    @pytest.mark.asyncio
    async def test_search_across_multiple_agents(self) -> None:
        repo = InMemoryMemoryRepository()
        m1 = MemoryItem(
            item_id="m-s1",
            tenant_id="t-1",
            agent_instance_id="a1",
            type=MemoryType.FACT,
            content="Uses PostgreSQL for storage",
            confidence=0.9,
            source="s",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        m2 = MemoryItem(
            item_id="m-s2",
            tenant_id="t-1",
            agent_instance_id="a2",
            type=MemoryType.PREFERENCE,
            content="Prefers PostgreSQL over MySQL",
            confidence=0.7,
            source="s",
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        await repo.save(m1)
        await repo.save(m2)

        all_results = await repo.search("PostgreSQL")
        assert len(all_results) == 2

        a1_results = await repo.search("PostgreSQL", agent_instance_id="a1")
        assert len(a1_results) == 1
        assert a1_results[0].item_id == "m-s1"

    @pytest.mark.asyncio
    async def test_delete_then_get_returns_none(self) -> None:
        repo = InMemoryMemoryRepository()
        mem = MemoryItem(
            item_id="mem-del",
            tenant_id="t-1",
            agent_instance_id="a1",
            type=MemoryType.FACT,
            content="to be deleted",
            confidence=1.0,
            source="s",
            created_at=datetime(2026, 7, 12, tzinfo=timezone.utc),
        )
        await repo.save(mem)

        await repo.delete("mem-del")
        result = await repo.get("mem-del")
        assert result is None
