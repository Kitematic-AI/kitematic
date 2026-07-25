"""Tests for PluginExecutor — permission checks and timeout dispatch."""

from typing import Any

import pytest

from agents.loader.executor import PluginExecutor
from agents.loader.runtime import PluginRuntimeManager
from core.domain.capability_binding import CapabilityBinding
from core.domain.plugin import PluginManifest, PluginType

# ── Fake Plugin ───────────────────────────────────────────────────────────────


class FakeSlowPlugin:
    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    async def health_check(self) -> bool:
        return True

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"result": payload.get("data", "ok")}


class FakeTimeoutPlugin:
    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    async def health_check(self) -> bool:
        return True

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        import asyncio
        await asyncio.sleep(10)
        return {}


# ── Helpers ───────────────────────────────────────────────────────────────────


_MODULE = "tests.agents.loader.test_executor"


def _manifest(class_name: str = "FakeSlowPlugin") -> PluginManifest:
    return PluginManifest(
        name="test-plugin",
        version="1.0.0",
        plugin_type=PluginType.TOOL,
        runtime_type="test-runtime",
        description="Test plugin",
        author="Test",
        entrypoint={"module": _MODULE, "class": class_name},
    )


def _binding(*perms: str, name: str = "test-plugin") -> CapabilityBinding:
    return CapabilityBinding(
        plugin_name=name,
        capability_name="test",
        permissions=perms,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestPermissionValidation:
    async def test_allows_with_sufficient_permissions(self) -> None:
        runtime = PluginRuntimeManager()
        await runtime.load(_manifest())
        executor = PluginExecutor(runtime)

        result = await executor.execute(
            "test-plugin",
            {"data": "hello"},
            bindings=[_binding("filesystem.read")],
            requested_permissions={"filesystem.read"},
        )
        assert result == {"result": "hello"}

    async def test_denies_without_permissions(self) -> None:
        runtime = PluginRuntimeManager()
        await runtime.load(_manifest())
        executor = PluginExecutor(runtime)

        with pytest.raises(PermissionError, match="missing permissions"):
            await executor.execute(
                "test-plugin",
                {},
                bindings=[_binding("filesystem.read")],
                requested_permissions={"network.egress"},
            )

    async def test_empty_bindings_deny_all(self) -> None:
        runtime = PluginRuntimeManager()
        await runtime.load(_manifest())
        executor = PluginExecutor(runtime)

        with pytest.raises(PermissionError, match="missing permissions"):
            await executor.execute(
                "test-plugin",
                {},
                bindings=[],
                requested_permissions={"anything"},
            )

    async def test_no_requested_permissions_skips_check(self) -> None:
        runtime = PluginRuntimeManager()
        await runtime.load(_manifest())
        executor = PluginExecutor(runtime)

        result = await executor.execute(
            "test-plugin",
            {"data": "ok"},
            bindings=[],
        )
        assert result == {"result": "ok"}


class TestTimeout:
    async def test_honours_timeout(self) -> None:
        runtime = PluginRuntimeManager()
        await runtime.load(_manifest("FakeTimeoutPlugin"))
        executor = PluginExecutor(runtime)

        with pytest.raises(TimeoutError, match="timed out"):
            await executor.execute(
                "test-plugin",
                {},
                timeout_seconds=0.1,
            )

    async def test_no_timeout_when_zero(self) -> None:
        runtime = PluginRuntimeManager()
        await runtime.load(_manifest())
        executor = PluginExecutor(runtime)

        result = await executor.execute("test-plugin", {"data": "ok"})
        assert result == {"result": "ok"}


class TestErrorPropagation:
    async def test_unregistered_plugin_raises(self) -> None:
        runtime = PluginRuntimeManager()
        executor = PluginExecutor(runtime)

        with pytest.raises(KeyError, match="not loaded"):
            await executor.execute("unknown", {})
