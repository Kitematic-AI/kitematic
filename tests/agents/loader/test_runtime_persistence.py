"""Tests for Plugin Runtime Manager persistence integration."""

from datetime import datetime
from typing import Any

import pytest

from agents.loader.runtime import (
    EVENT_FAILED,
    EVENT_LOADED,
    EVENT_STARTED,
    EVENT_STOPPED,
    PluginRuntimeManager,
    PluginRuntimeState,
)
from core.domain.plugin import PluginManifest, PluginType
from core.domain.plugin_runtime import PluginRuntimeRecord

# ── Fake Store ────────────────────────────────────────────────────────────────


class FakeStore:
    def __init__(self) -> None:
        self.records: dict[str, PluginRuntimeRecord] = {}

    async def save(self, record: PluginRuntimeRecord) -> None:
        self.records[record.name] = record

    async def get(self, name: str) -> PluginRuntimeRecord | None:
        return self.records.get(name)

    async def list_all(self) -> list[PluginRuntimeRecord]:
        return list(self.records.values())

    async def remove(self, name: str) -> None:
        self.records.pop(name, None)


# ── Fake Plugin ───────────────────────────────────────────────────────────────


class FakeFullPlugin:
    def __init__(self) -> None:
        self.initialized = False
        self.shutdown_called = False

    async def initialize(self) -> None:
        self.initialized = True

    async def shutdown(self) -> None:
        self.shutdown_called = True

    async def health_check(self) -> bool:
        return True

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"echo": payload}


class FakeFailingPlugin:
    async def initialize(self) -> None:
        raise RuntimeError("init crashed")

    async def shutdown(self) -> None:
        pass

    async def health_check(self) -> bool:
        return True

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {}


# ── Helpers ───────────────────────────────────────────────────────────────────


_MODULE = "tests.agents.loader.test_runtime_persistence"


def _manifest(
    name: str = "test-plugin",
    class_name: str = "FakeFullPlugin",
    module: str | None = None,
) -> PluginManifest:
    return PluginManifest(
        name=name,
        version="1.0.0",
        plugin_type=PluginType.TOOL,
        runtime_type="test-runtime",
        description="Test plugin",
        author="Test",
        entrypoint={"module": module or _MODULE, "class": class_name},
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestPersistLoad:
    async def test_load_persists_running(self) -> None:
        store = FakeStore()
        manager = PluginRuntimeManager(store)

        await manager.load(_manifest())

        record = await store.get("test-plugin")
        assert record is not None
        assert record.name == "test-plugin"
        assert record.state == PluginRuntimeState.RUNNING
        assert record.loaded_at is not None

    async def test_load_without_store_still_works(self) -> None:
        manager = PluginRuntimeManager()

        await manager.load(_manifest())

        assert manager.state("test-plugin") == PluginRuntimeState.RUNNING
        assert manager.loaded_count == 1

    async def test_failed_import_persists_failed(self) -> None:
        store = FakeStore()
        manager = PluginRuntimeManager(store)

        with pytest.raises(ValueError, match="cannot import module"):
            await manager.load(_manifest(module="nonexistent.module"))

        record = await store.get("test-plugin")
        assert record is not None
        assert record.state == PluginRuntimeState.FAILED
        assert record.error is not None
        assert "No module named" in record.error

    async def test_initialize_failure_persists_failed(self) -> None:
        store = FakeStore()
        manager = PluginRuntimeManager(store)

        with pytest.raises(RuntimeError, match="init crashed"):
            await manager.load(_manifest(class_name="FakeFailingPlugin"))

        record = await store.get("test-plugin")
        assert record is not None
        assert record.state == PluginRuntimeState.FAILED
        assert record.error == "init crashed"

    async def test_load_emits_loaded_and_started_events(self) -> None:
        manager = PluginRuntimeManager()

        await manager.load(_manifest())

        event_types = [e.event_type for e in manager.events]
        assert EVENT_LOADED in event_types
        assert EVENT_STARTED in event_types


class TestPersistShutdown:
    async def test_shutdown_persists_stopped(self) -> None:
        store = FakeStore()
        manager = PluginRuntimeManager(store)

        await manager.load(_manifest())
        await manager.shutdown("test-plugin")

        record = await store.get("test-plugin")
        assert record is not None
        assert record.state == PluginRuntimeState.STOPPED

    async def test_shutdown_emits_stopped_event(self) -> None:
        manager = PluginRuntimeManager()

        await manager.load(_manifest())
        await manager.shutdown("test-plugin")

        assert any(e.event_type == EVENT_STOPPED for e in manager.events)

    async def test_shutdown_all_persists_all(self) -> None:
        store = FakeStore()
        manager = PluginRuntimeManager(store)

        await manager.load(_manifest("alpha"))
        await manager.load(_manifest("beta"))
        await manager.shutdown_all()

        alpha = await store.get("alpha")
        beta = await store.get("beta")
        assert alpha is not None and alpha.state == PluginRuntimeState.STOPPED
        assert beta is not None and beta.state == PluginRuntimeState.STOPPED


class TestPersistHealth:
    async def test_health_updates_timestamp(self) -> None:
        store = FakeStore()
        manager = PluginRuntimeManager(store)

        await manager.load(_manifest())
        record_before = await store.get("test-plugin")
        assert record_before is not None
        ts_before = record_before.last_health_check

        await manager.health_check()

        record_after = await store.get("test-plugin")
        assert record_after is not None
        # timestamp should have been updated
        assert record_after.last_health_check is not None
        assert record_after.last_health_check != ts_before


class TestEvents:
    async def test_events_property_returns_copy(self) -> None:
        manager = PluginRuntimeManager()

        await manager.load(_manifest())
        events_copy = manager.events
        assert len(events_copy) >= 2  # loaded + started
        # Modify the copy — original should be unchanged
        events_copy.clear()
        assert len(manager.events) >= 2

    async def test_failure_emits_failed_event(self) -> None:
        manager = PluginRuntimeManager()

        with pytest.raises(ValueError):
            await manager.load(_manifest(module="nonexistent.module"))

        assert any(e.event_type == EVENT_FAILED for e in manager.events)
