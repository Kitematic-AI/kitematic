"""Tests for MemoryItem domain model."""

from datetime import UTC, datetime, timedelta

from core.domain.memory import MemoryItem, MemoryType


class TestMemoryItem:
    def test_valid_memory_passes_validation(self) -> None:
        item = MemoryItem(
            item_id="mem-1",
            tenant_id="tenant-abc",
            agent_instance_id="agent-1",
            type=MemoryType.FACT,
            content="Customer prefers email communication",
            confidence=0.92,
        )
        errors = item.validate()
        assert len(errors) == 0
        assert item.is_valid is True

    def test_missing_content_fails(self) -> None:
        item = MemoryItem(
            item_id="mem-2",
            tenant_id="t-1",
            agent_instance_id="a-1",
            type=MemoryType.SUMMARY,
            content="",
        )
        errors = item.validate()
        assert any("content" in e for e in errors)

    def test_confidence_range(self) -> None:
        item = MemoryItem(
            item_id="mem-3",
            tenant_id="t-1",
            agent_instance_id="a-1",
            type=MemoryType.FACT,
            content="test",
            confidence=1.5,
        )
        errors = item.validate()
        assert any("confidence" in e for e in errors)

    def test_expired_check(self) -> None:
        past = datetime(2025, 1, 1, tzinfo=UTC)
        item = MemoryItem(
            item_id="mem-4",
            tenant_id="t-1",
            agent_instance_id="a-1",
            type=MemoryType.EXPERIENCE,
            content="test experience",
            created_at=past,
            expires_at=past + timedelta(hours=1),
        )
        assert item.is_expired is True

    def test_no_expiry(self) -> None:
        item = MemoryItem(
            item_id="mem-5",
            tenant_id="t-1",
            agent_instance_id="a-1",
            type=MemoryType.FACT,
            content="permanent fact",
        )
        assert item.is_expired is False
