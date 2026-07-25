"""Tests for plugin lifecycle manager."""

from typing import Any

import pytest

from agents.loader.lifecycle import PluginLifecycleManager
from agents.loader.runtime import PluginRuntimeManager
from core.domain.plugin import PluginManifest, PluginType

# ── Fakes ─────────────────────────────────────────────────────────────────────


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


class FakeFailingPlugin:
    """initialize() raises an exception."""

    async def initialize(self) -> None:
        raise RuntimeError("init failure")

    async def shutdown(self) -> None:
        pass

    async def health_check(self) -> bool:
        return True

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {}


class FakeNoLifecyclePlugin:
    """Does not implement PluginLifecycleProtocol."""

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {}


class FakeCapabilityStore:
    def __init__(self) -> None:
        self.capabilities: dict[str, list[dict[str, Any]]] = {}

    async def add_capabilities(self, plugin_name: str, caps: list[dict[str, Any]]) -> None:
        self.capabilities[plugin_name] = caps

    async def remove_capabilities(self, plugin_name: str) -> None:
        self.capabilities.pop(plugin_name, None)


class FakeToolRegistry:
    def __init__(self) -> None:
        self.tools: dict[str, dict[str, str]] = {}

    def register_tool(self, tool_id: str, entrypoint: dict[str, str]) -> None:
        self.tools[tool_id] = entrypoint

    def unregister_tool(self, tool_id: str) -> None:
        self.tools.pop(tool_id, None)


class FakePolicyEvaluator:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed
        self.evaluated: list[list[dict[str, Any]]] = []

    async def evaluate_capabilities(
        self,
        capabilities: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
    ) -> bool:
        self.evaluated.append(capabilities)
        return self.allowed


# ── Helpers ───────────────────────────────────────────────────────────────────


_MODULE = "tests.agents.loader.test_lifecycle"


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
        entrypoint={
            "module": module or _MODULE,
            "class": class_name,
        },
        capabilities=[
            {"name": "test.cap", "risk_level": "low", "permissions": ["test.perm"]},
        ],
        permissions=["test.perm"],
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestActivate:
    async def test_activate_full_success(self) -> None:
        store = FakeCapabilityStore()
        registry = FakeToolRegistry()
        runtime = PluginRuntimeManager()
        lifecycle = PluginLifecycleManager(runtime, store, registry)

        result = await lifecycle.activate(_manifest())

        assert result.success
        assert result.plugin_name == "test-plugin"
        # Registered
        assert "test-plugin" in store.capabilities
        assert "test-plugin" in registry.tools
        # Runtime loaded
        assert runtime.state("test-plugin").value == "running"
        assert runtime.loaded_count == 1

    async def test_activate_policy_rejected_does_not_load(self) -> None:
        store = FakeCapabilityStore()
        registry = FakeToolRegistry()
        runtime = PluginRuntimeManager()
        policy = FakePolicyEvaluator(allowed=False)
        lifecycle = PluginLifecycleManager(runtime, store, registry, policy)

        result = await lifecycle.activate(_manifest())

        assert not result.success
        assert "rejected by policy" in result.errors[0]
        # Nothing registered
        assert "test-plugin" not in store.capabilities
        # Runtime not loaded
        assert runtime.loaded_count == 0

    async def test_activate_runtime_failure_rolls_back_registration(self) -> None:
        store = FakeCapabilityStore()
        registry = FakeToolRegistry()
        runtime = PluginRuntimeManager()
        lifecycle = PluginLifecycleManager(runtime, store, registry)

        # Plugin that fails initialize
        result = await lifecycle.activate(_manifest(class_name="FakeFailingPlugin"))

        assert not result.success
        assert "init failure" in result.errors[0]
        # Registration was rolled back
        assert "test-plugin" not in store.capabilities
        assert "test-plugin" not in registry.tools
        # Runtime didn't load
        assert runtime.loaded_count == 0

    async def test_activate_non_conforming_plugin_rolls_back(self) -> None:
        store = FakeCapabilityStore()
        registry = FakeToolRegistry()
        runtime = PluginRuntimeManager()
        lifecycle = PluginLifecycleManager(runtime, store, registry)

        result = await lifecycle.activate(_manifest(class_name="FakeNoLifecyclePlugin"))

        assert not result.success
        assert "does not implement" in result.errors[0]
        # Registration rolled back
        assert "test-plugin" not in store.capabilities
        assert "test-plugin" not in registry.tools

    async def test_activate_nonexistent_module_rolls_back(self) -> None:
        store = FakeCapabilityStore()
        registry = FakeToolRegistry()
        runtime = PluginRuntimeManager()
        lifecycle = PluginLifecycleManager(runtime, store, registry)

        result = await lifecycle.activate(_manifest(module="nonexistent.module"))

        assert not result.success
        assert "cannot import module" in result.errors[0]
        # Registration rolled back
        assert "test-plugin" not in store.capabilities
        assert "test-plugin" not in registry.tools


class TestDeactivate:
    async def test_deactivate_shutdown_then_unregister(self) -> None:
        store = FakeCapabilityStore()
        registry = FakeToolRegistry()
        runtime = PluginRuntimeManager()
        lifecycle = PluginLifecycleManager(runtime, store, registry)

        await lifecycle.activate(_manifest())
        plugin: FakeFullPlugin = runtime._plugins["test-plugin"]

        await lifecycle.deactivate("test-plugin")

        # Runtime shut down
        assert plugin.shutdown_called
        assert runtime.state("test-plugin").value == "stopped"
        # Unregistered
        assert "test-plugin" not in store.capabilities
        assert "test-plugin" not in registry.tools

    async def test_deactivate_nonexistent_does_not_raise(self) -> None:
        store = FakeCapabilityStore()
        registry = FakeToolRegistry()
        runtime = PluginRuntimeManager()
        lifecycle = PluginLifecycleManager(runtime, store, registry)

        # Should not raise
        await lifecycle.deactivate("nonexistent")
