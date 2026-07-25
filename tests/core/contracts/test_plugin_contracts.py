"""Tests for plugin runtime contracts."""

from typing import Any

from core.contracts.plugin import (
    PluginExecutableProtocol,
    PluginHealthProtocol,
    PluginLifecycleProtocol,
)


class _GoodPlugin:
    """Fully conforming plugin — implements all three protocols."""

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    async def health_check(self) -> bool:
        return True

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"result": payload.get("data", "ok")}


class TestPluginLifecycleProtocol:
    def test_protocol_exists(self) -> None:
        assert PluginLifecycleProtocol is not None

    def test_conforming_class_passes_isinstance_check(self) -> None:
        plugin = _GoodPlugin()
        assert isinstance(plugin, PluginLifecycleProtocol)

    def test_non_conforming_class_fails_isinstance_check(self) -> None:
        class _Bad:
            pass

        assert not isinstance(_Bad(), PluginLifecycleProtocol)


class TestPluginHealthProtocol:
    def test_protocol_exists(self) -> None:
        assert PluginHealthProtocol is not None

    def test_conforming_class_passes_isinstance_check(self) -> None:
        plugin = _GoodPlugin()
        assert isinstance(plugin, PluginHealthProtocol)

    def test_health_check_returns_bool(self) -> None:
        plugin = _GoodPlugin()
        import asyncio
        result = asyncio.run(plugin.health_check())
        assert result is True


class TestPluginExecutableProtocol:
    def test_protocol_exists(self) -> None:
        assert PluginExecutableProtocol is not None

    def test_conforming_class_passes_isinstance_check(self) -> None:
        plugin = _GoodPlugin()
        assert isinstance(plugin, PluginExecutableProtocol)

    def test_execute_roundtrip(self) -> None:
        plugin = _GoodPlugin()
        import asyncio
        result = asyncio.run(plugin.execute({"data": "hello"}))
        assert result == {"result": "hello"}
