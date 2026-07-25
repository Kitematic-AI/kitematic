"""Runtime executor contract — SPI for executing plugins with context.

The Executor layer uses this protocol to decouple permission validation
from the actual plugin execution mechanism.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from core.domain.execution_context import ExecutionContext


@runtime_checkable
class RuntimeExecutorProtocol(Protocol):
    """Execution interface that respects capability boundaries."""

    async def execute(
        self,
        plugin_name: str,
        payload: dict[str, Any],
        context: ExecutionContext,
    ) -> dict[str, Any]:
        ...
