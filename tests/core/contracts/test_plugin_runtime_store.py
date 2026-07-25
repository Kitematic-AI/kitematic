"""Tests for PluginRuntimeStore protocol and RuntimeEvent."""

from datetime import datetime

import pytest

from core.contracts.plugin_runtime import PluginRuntimeStore
from core.domain.plugin_runtime import PluginRuntimeRecord, PluginRuntimeState
from core.domain.runtime_event import RuntimeEvent


class TestPluginRuntimeStoreProtocol:
    def test_protocol_exists(self) -> None:
        assert PluginRuntimeStore is not None

    def test_conforming_store_passes_isinstance(self) -> None:
        class InMemoryStore:
            async def save(self, record: PluginRuntimeRecord) -> None:
                pass
            async def get(self, name: str) -> PluginRuntimeRecord | None:
                return None
            async def list_all(self) -> list[PluginRuntimeRecord]:
                return []
            async def remove(self, name: str) -> None:
                pass

        assert isinstance(InMemoryStore(), PluginRuntimeStore)

    def test_non_conforming_class_fails_isinstance(self) -> None:
        class Bad:
            pass

        assert not isinstance(Bad(), PluginRuntimeStore)


class TestPluginRuntimeEvent:
    def test_create_event(self) -> None:
        ts = datetime(2026, 7, 25, 10, 0, 0)
        event = RuntimeEvent(
            plugin_name="test",
            event_type="loaded",
            timestamp=ts,
        )
        assert event.plugin_name == "test"
        assert event.event_type == "loaded"
        assert event.timestamp == ts

    def test_event_with_metadata(self) -> None:
        event = RuntimeEvent(
            plugin_name="test",
            event_type="failed",
            timestamp=datetime(2026, 7, 25, 10, 0, 0),
            metadata={"error": "timeout"},
        )
        assert event.metadata["error"] == "timeout"

    def test_event_frozen(self) -> None:
        event = RuntimeEvent(
            plugin_name="test",
            event_type="loaded",
            timestamp=datetime(2026, 7, 25, 10, 0, 0),
        )
        with pytest.raises(AttributeError):
            event.plugin_name = "other"

    def test_event_default_metadata_is_none(self) -> None:
        event = RuntimeEvent(
            plugin_name="test",
            event_type="loaded",
            timestamp=datetime(2026, 7, 25, 10, 0, 0),
        )
        assert event.metadata is None

    def test_event_frozen_prevents_reassignment(self) -> None:
        event = RuntimeEvent(
            plugin_name="test",
            event_type="loaded",
            timestamp=datetime(2026, 7, 25, 10, 0, 0),
            metadata={"version": "1.0"},
        )
        with pytest.raises(AttributeError):
            event.metadata = {"new": "dict"}

    def test_event_types(self) -> None:
        for event_type in ("loaded", "started", "failed", "stopped", "health_ok", "health_fail"):
            event = RuntimeEvent(
                plugin_name="test",
                event_type=event_type,
                timestamp=datetime(2026, 7, 25, 10, 0, 0),
            )
            assert event.event_type == event_type
