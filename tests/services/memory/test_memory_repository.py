"""Unit tests for InMemoryMemoryRepository."""

from datetime import datetime, timedelta, timezone

import pytest

from runtime.domain.memory import MemoryItem, MemoryType
from services.memory.repositories.in_memory_memory import InMemoryMemoryRepository


def _make_memory(
    item_id: str = "mem-1",
    agent_instance_id: str = "agent-1",
    content: str = "test memory",
    memory_type: MemoryType = MemoryType.FACT,
    confidence: float = 1.0,
    created_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> MemoryItem:
    return MemoryItem(
        item_id=item_id,
        tenant_id="t-1",
        agent_instance_id=agent_instance_id,
        type=memory_type,
        content=content,
        confidence=confidence,
        source="test",
        created_at=created_at or datetime(2026, 1, 1, tzinfo=timezone.utc),
        expires_at=expires_at,
    )


def _past_item(item_id: str = "mem-exp", **overrides) -> MemoryItem:
    past = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return _make_memory(
        item_id=item_id,
        created_at=past,
        expires_at=past + timedelta(hours=1),
        **overrides,
    )


class TestMemoryRepositorySaveAndGet:
    @pytest.mark.asyncio
    async def test_save_and_get_roundtrip(self) -> None:
        repo = InMemoryMemoryRepository()
        mem = _make_memory()
        await repo.save(mem)
        result = await repo.get("mem-1")

        assert result is not None
        assert result.item_id == "mem-1"
        assert result.agent_instance_id == "agent-1"
        assert result.content == "test memory"
        assert result.type == MemoryType.FACT

    @pytest.mark.asyncio
    async def test_get_returns_none_for_unknown_id(self) -> None:
        repo = InMemoryMemoryRepository()
        result = await repo.get("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_returns_none_for_expired(self) -> None:
        repo = InMemoryMemoryRepository()
        mem = _past_item()
        await repo.save(mem)
        result = await repo.get("mem-exp")
        assert result is None


class TestMemoryRepositoryListByAgent:
    @pytest.mark.asyncio
    async def test_list_by_agent_returns_agent_memories(self) -> None:
        repo = InMemoryMemoryRepository()
        m1 = _make_memory(item_id="m1", agent_instance_id="a1")
        m2 = _make_memory(item_id="m2", agent_instance_id="a1")
        m3 = _make_memory(item_id="m3", agent_instance_id="a2")
        await repo.save(m1)
        await repo.save(m2)
        await repo.save(m3)

        result = await repo.list_by_agent("a1")
        assert len(result) == 2
        assert all(m.agent_instance_id == "a1" for m in result)

    @pytest.mark.asyncio
    async def test_list_by_agent_excludes_expired(self) -> None:
        repo = InMemoryMemoryRepository()
        good = _make_memory(item_id="good", agent_instance_id="a1")
        expired = _past_item(item_id="expired", agent_instance_id="a1")
        await repo.save(good)
        await repo.save(expired)

        result = await repo.list_by_agent("a1")
        assert len(result) == 1
        assert result[0].item_id == "good"

    @pytest.mark.asyncio
    async def test_list_by_agent_returns_empty_for_unknown(self) -> None:
        repo = InMemoryMemoryRepository()
        result = await repo.list_by_agent("unknown-agent")
        assert result == []


class TestMemoryRepositorySearch:
    @pytest.mark.asyncio
    async def test_search_by_content_substring(self) -> None:
        repo = InMemoryMemoryRepository()
        m1 = _make_memory(item_id="m1", content="Customer prefers email")
        m2 = _make_memory(item_id="m2", content="System uses Python")
        await repo.save(m1)
        await repo.save(m2)

        result = await repo.search("email")
        assert len(result) == 1
        assert result[0].item_id == "m1"

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self) -> None:
        repo = InMemoryMemoryRepository()
        mem = _make_memory(item_id="m1", content="Hello World")
        await repo.save(mem)

        result = await repo.search("hello")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_filters_by_agent(self) -> None:
        repo = InMemoryMemoryRepository()
        m1 = _make_memory(item_id="m1", agent_instance_id="a1", content="fact one")
        m2 = _make_memory(item_id="m2", agent_instance_id="a2", content="fact two")
        await repo.save(m1)
        await repo.save(m2)

        result = await repo.search("fact", agent_instance_id="a1")
        assert len(result) == 1
        assert result[0].item_id == "m1"

    @pytest.mark.asyncio
    async def test_search_filters_by_type(self) -> None:
        repo = InMemoryMemoryRepository()
        m1 = _make_memory(item_id="m1", content="some fact", memory_type=MemoryType.FACT)
        m2 = _make_memory(item_id="m2", content="some pref", memory_type=MemoryType.PREFERENCE)
        await repo.save(m1)
        await repo.save(m2)

        result = await repo.search("some", memory_type=MemoryType.PREFERENCE)
        assert len(result) == 1
        assert result[0].item_id == "m2"

    @pytest.mark.asyncio
    async def test_search_filters_by_confidence(self) -> None:
        repo = InMemoryMemoryRepository()
        m1 = _make_memory(item_id="m1", content="confident", confidence=0.9)
        m2 = _make_memory(item_id="m2", content="uncertain", confidence=0.3)
        await repo.save(m1)
        await repo.save(m2)

        result = await repo.search("conf", min_confidence=0.5)
        assert len(result) == 1
        assert result[0].item_id == "m1"

    @pytest.mark.asyncio
    async def test_search_excludes_expired(self) -> None:
        repo = InMemoryMemoryRepository()
        good = _make_memory(item_id="good", content="valid memory")
        expired = _past_item(item_id="expired", content="expired memory")
        await repo.save(good)
        await repo.save(expired)

        result = await repo.search("memory")
        assert len(result) == 1
        assert result[0].item_id == "good"


class TestMemoryRepositoryDelete:
    @pytest.mark.asyncio
    async def test_delete_removes_item(self) -> None:
        repo = InMemoryMemoryRepository()
        mem = _make_memory()
        await repo.save(mem)
        await repo.delete("mem-1")
        result = await repo.get("mem-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_unknown_is_noop(self) -> None:
        repo = InMemoryMemoryRepository()
        await repo.delete("nonexistent")  # should not raise


class TestMemoryRepositoryImmutability:
    @pytest.mark.asyncio
    async def test_save_immutable(self) -> None:
        repo = InMemoryMemoryRepository()
        mem = _make_memory()
        await repo.save(mem)

        object.__setattr__(mem, "content", "modified")
        stored = await repo.get("mem-1")
        assert stored is not None
        assert stored.content == "test memory"

    @pytest.mark.asyncio
    async def test_get_returns_copy(self) -> None:
        repo = InMemoryMemoryRepository()
        mem = _make_memory()
        await repo.save(mem)

        returned = await repo.get("mem-1")
        assert returned is not None
        object.__setattr__(returned, "content", "modified")

        stored = await repo.get("mem-1")
        assert stored is not None
        assert stored.content == "test memory"

    @pytest.mark.asyncio
    async def test_list_ordered_by_created_at(self) -> None:
        repo = InMemoryMemoryRepository()
        t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        t2 = datetime(2026, 6, 1, tzinfo=timezone.utc)
        t3 = datetime(2026, 3, 1, tzinfo=timezone.utc)

        m1 = _make_memory(item_id="m1", created_at=t1)
        m2 = _make_memory(item_id="m2", created_at=t2)
        m3 = _make_memory(item_id="m3", created_at=t3)
        await repo.save(m2)
        await repo.save(m3)
        await repo.save(m1)

        result = await repo.list_by_agent("agent-1")
        ids = [m.item_id for m in result]
        assert ids == ["m1", "m3", "m2"]
