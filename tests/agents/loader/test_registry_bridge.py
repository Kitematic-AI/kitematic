"""Tests for registry bridge."""

from typing import Any

import pytest

from agents.loader.registry_bridge import (
    RegistrationResult,
    register,
    unregister,
)
from core.domain.plugin import PluginManifest, PluginType


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
        self.evaluated_capabilities: list[list[dict[str, Any]]] = []

    async def evaluate_capabilities(
        self,
        capabilities: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
    ) -> bool:
        self.evaluated_capabilities.append(capabilities)
        return self.allowed


def _make_manifest(name: str = "test-plugin") -> PluginManifest:
    return PluginManifest(
        name=name,
        version="1.0.0",
        plugin_type=PluginType.TOOL,
        runtime_type="test-runtime",
        description="Test plugin",
        author="Test Author",
        entrypoint={"module": "test", "class": "Test"},
        capabilities=[
            {"name": "test.cap", "risk_level": "low", "permissions": ["test.perm"]},
        ],
        permissions=["test.perm"],
    )


class TestRegister:
    async def test_register_without_policy(self) -> None:
        manifest = _make_manifest("simple")
        store = FakeCapabilityStore()
        registry = FakeToolRegistry()
        result = await register(manifest, store, registry)
        assert result.success
        assert store.capabilities["simple"] == manifest.capabilities
        assert registry.tools["simple"] == manifest.entrypoint

    async def test_register_with_policy_allowed(self) -> None:
        manifest = _make_manifest("policy-allowed")
        store = FakeCapabilityStore()
        registry = FakeToolRegistry()
        policy = FakePolicyEvaluator(allowed=True)
        result = await register(manifest, store, registry, policy)
        assert result.success
        assert len(policy.evaluated_capabilities) == 1

    async def test_register_with_policy_rejected(self) -> None:
        manifest = _make_manifest("policy-rejected")
        store = FakeCapabilityStore()
        registry = FakeToolRegistry()
        policy = FakePolicyEvaluator(allowed=False)
        result = await register(manifest, store, registry, policy)
        assert not result.success
        assert "rejected by policy" in result.errors[0]
        # Should NOT have registered anything
        assert "policy-rejected" not in store.capabilities
        assert "policy-rejected" not in registry.tools

    async def test_register_duplicate_overwrites(self) -> None:
        manifest = _make_manifest("duplicate")
        store = FakeCapabilityStore()
        registry = FakeToolRegistry()
        await register(manifest, store, registry)
        await register(manifest, store, registry)
        assert store.capabilities["duplicate"] == manifest.capabilities

    async def test_registration_result_repr(self) -> None:
        result = RegistrationResult(success=True, plugin_name="ok")
        assert result.plugin_name == "ok"

        error_result = RegistrationResult(
            success=False, plugin_name="bad", errors=["something went wrong"]
        )
        assert not error_result.success
        assert "something went wrong" in error_result.errors


class TestUnregister:
    async def test_unregister_removes_everything(self) -> None:
        manifest = _make_manifest("to-remove")
        store = FakeCapabilityStore()
        registry = FakeToolRegistry()
        await register(manifest, store, registry)
        await unregister("to-remove", store, registry)
        assert "to-remove" not in store.capabilities
        assert "to-remove" not in registry.tools

    async def test_unregister_nonexistent(self) -> None:
        store = FakeCapabilityStore()
        registry = FakeToolRegistry()
        await unregister("nonexistent", store, registry)  # Should not raise

    async def test_unregister_only_one(self) -> None:
        store = FakeCapabilityStore()
        registry = FakeToolRegistry()
        m1 = _make_manifest("keep-me")
        m2 = _make_manifest("remove-me")
        await register(m1, store, registry)
        await register(m2, store, registry)
        await unregister("remove-me", store, registry)
        assert "keep-me" in store.capabilities
        assert "keep-me" in registry.tools
        assert "remove-me" not in store.capabilities
        assert "remove-me" not in registry.tools
