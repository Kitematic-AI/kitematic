"""Tests for Plugin Runtime Manager."""

from typing import Any

import pytest

from agents.loader.runtime import PluginRuntimeManager, PluginRuntimeState
from core.domain.plugin import PluginManifest, PluginType

# ── Fake plugins ──────────────────────────────────────────────────────────────


class FakeFullPlugin:
    """Implements all three runtime protocols."""

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


class FakeNoLifecycle:
    """Does NOT implement PluginLifecycleProtocol."""

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {}


class FakeFailingInit:
    """initialize() raises an exception."""

    async def initialize(self) -> None:
        raise RuntimeError("init failed")

    async def shutdown(self) -> None:
        pass

    async def health_check(self) -> bool:
        return True

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _manifest(
    name: str = "test-plugin",
    module: str = "tests.agents.loader.test_runtime",
    class_name: str = "FakeFullPlugin",
) -> PluginManifest:
    return PluginManifest(
        name=name,
        version="1.0.0",
        plugin_type=PluginType.TOOL,
        runtime_type="test-runtime",
        description="Test plugin",
        author="Test",
        entrypoint={"module": module, "class": class_name},
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestLoad:
    async def test_load_sets_running_state(self) -> None:
        manager = PluginRuntimeManager()
        manifest = _manifest()
        await manager.load(manifest)
        assert manager.state("test-plugin") == PluginRuntimeState.RUNNING
        assert manager.loaded_count == 1

    async def test_load_calls_initialize(self) -> None:
        manager = PluginRuntimeManager()
        manifest = _manifest(class_name="FakeFullPlugin")
        await manager.load(manifest)
        plugin: FakeFullPlugin = manager._plugins["test-plugin"]
        assert plugin.initialized is True

    async def test_load_rejects_non_conforming_class(self) -> None:
        manager = PluginRuntimeManager()
        manifest = _manifest(class_name="FakeNoLifecycle")
        with pytest.raises(ValueError, match="does not implement PluginLifecycleProtocol"):
            await manager.load(manifest)
        assert manager.state("test-plugin") == PluginRuntimeState.FAILED

    async def test_load_nonexistent_module(self) -> None:
        manager = PluginRuntimeManager()
        manifest = _manifest(module="nonexistent.module")
        with pytest.raises(ValueError, match="cannot import module"):
            await manager.load(manifest)
        assert manager.state("test-plugin") == PluginRuntimeState.FAILED

    async def test_load_nonexistent_class(self) -> None:
        manager = PluginRuntimeManager()
        manifest = _manifest(class_name="NonExistentClass")
        with pytest.raises(ValueError, match="not found in module"):
            await manager.load(manifest)
        assert manager.state("test-plugin") == PluginRuntimeState.FAILED


class TestExecute:
    async def test_execute_dispatch(self) -> None:
        manager = PluginRuntimeManager()
        await manager.load(_manifest())
        result = await manager.execute("test-plugin", {"hello": "world"})
        assert result == {"echo": {"hello": "world"}}

    async def test_execute_unregistered_raises(self) -> None:
        manager = PluginRuntimeManager()
        with pytest.raises(KeyError, match="not loaded"):
            await manager.execute("unknown", {})

    async def test_execute_not_running_raises(self) -> None:
        manager = PluginRuntimeManager()
        # Load a good plugin, then override its state
        await manager.load(_manifest("good"))
        manager._states["good"] = PluginRuntimeState.STOPPED
        with pytest.raises(RuntimeError, match="not RUNNING"):
            await manager.execute("good", {})


class TestHealth:
    async def test_health_returns_true_for_healthy_plugin(self) -> None:
        manager = PluginRuntimeManager()
        await manager.load(_manifest())
        health = await manager.health_check()
        assert health == {"test-plugin": True}

    async def test_health_without_protocol_falls_back_to_state(self) -> None:
        """Plugins without PluginHealthProtocol still report based on state."""
        from agents.loader.runtime import PluginRuntimeManager

        class FakeExecOnly:
            async def initialize(self) -> None:
                pass
            async def shutdown(self) -> None:
                pass
            async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
                return {}

        # Register this as an inline test
        manager = PluginRuntimeManager()
        # Load directly into _plugins and set state
        plugin = FakeExecOnly()
        await plugin.initialize()
        manager._plugins["exec-only"] = plugin
        manager._states["exec-only"] = PluginRuntimeState.RUNNING

        health = await manager.health_check()
        assert health["exec-only"] is True


class TestShutdown:
    async def test_shutdown_all_stops_plugins(self) -> None:
        manager = PluginRuntimeManager()
        await manager.load(_manifest())
        assert manager.running_count == 1

        await manager.shutdown_all()
        assert manager.state("test-plugin") == PluginRuntimeState.STOPPED
        assert manager.running_count == 0

    async def test_shutdown_calls_shutdown_method(self) -> None:
        manager = PluginRuntimeManager()
        manifest = _manifest(class_name="FakeFullPlugin")
        await manager.load(manifest)
        plugin: FakeFullPlugin = manager._plugins["test-plugin"]
        assert plugin.shutdown_called is False

        await manager.shutdown_all()
        assert plugin.shutdown_called is True

    async def test_shutdown_does_not_raise_on_unloadable(self) -> None:
        """Plugins that crashed during load are skipped during shutdown."""
        manager = PluginRuntimeManager()
        # Load one good plugin
        await manager.load(_manifest("good"))
        # Simulate a plugin that failed at load
        manager._states["bad"] = PluginRuntimeState.FAILED
        await manager.shutdown_all()
        assert manager.state("good") == PluginRuntimeState.STOPPED


class TestState:
    async def test_initial_state(self) -> None:
        manager = PluginRuntimeManager()
        assert manager.state("nonexistent") is None
        assert manager.loaded_count == 0
        assert manager.running_count == 0

    async def test_state_transitions(self) -> None:
        manager = PluginRuntimeManager()
        manifest = _manifest(class_name="FakeFullPlugin")
        assert manager.state("test-plugin") is None
        await manager.load(manifest)
        assert manager.state("test-plugin") == PluginRuntimeState.RUNNING
        await manager.shutdown_all()
        assert manager.state("test-plugin") == PluginRuntimeState.STOPPED
