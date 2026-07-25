"""Plugin runtime contracts — interface boundaries for loadable plugins.

Every plugin (agent, tool, model, framework) must implement these protocols.
The Plugin Runtime Manager uses these contracts to manage plugin lifecycle.

Usage:
    class MyPlugin:
        async def initialize(self) -> None: ...
        async def shutdown(self) -> None: ...
        async def health_check(self) -> bool: ...
        async def execute(self, payload: dict[str, Any]) -> dict[str, Any]: ...
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PluginLifecycleProtocol(Protocol):
    """Lifecycle hooks every plugin must implement."""

    async def initialize(self) -> None:
        ...

    async def shutdown(self) -> None:
        ...


@runtime_checkable
class PluginHealthProtocol(Protocol):
    """Health check for liveness probes."""

    async def health_check(self) -> bool:
        ...


@runtime_checkable
class PluginExecutableProtocol(Protocol):
    """Core execution entrypoint for all plugins."""

    async def execute(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        ...
