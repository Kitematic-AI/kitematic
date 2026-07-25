"""Plugin runtime store contract — SPI for persisting runtime records.

Any storage backend (in-memory, file-based, Redis, SQL) implements this
protocol so that the RuntimeManager can persist and recover state.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from core.domain.plugin_runtime import PluginRuntimeRecord


@runtime_checkable
class PluginRuntimeStore(Protocol):
    """Persistence contract for plugin runtime records."""

    async def save(
        self,
        record: PluginRuntimeRecord,
    ) -> None:
        ...

    async def get(
        self,
        name: str,
    ) -> PluginRuntimeRecord | None:
        ...

    async def list_all(self) -> list[PluginRuntimeRecord]:
        ...

    async def remove(self, name: str) -> None:
        ...
