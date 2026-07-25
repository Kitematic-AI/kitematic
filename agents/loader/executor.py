"""Plugin executor — validates permissions then dispatches to runtime.

Enforces capability boundaries before any plugin code runs.
Supports timeout and permission checks as the gate.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from core.domain.capability_binding import CapabilityBinding
from core.domain.execution_context import ExecutionContext
from agents.loader.runtime import PluginRuntimeManager

logger = logging.getLogger("kitematic.loader.executor")


class PluginExecutor:
    """Permission-aware plugin execution dispatch.

    Flow:
        request → validate permissions → enforce timeout → runtime.execute()
    """

    def __init__(self, runtime: PluginRuntimeManager) -> None:
        self._runtime = runtime

    async def execute(
        self,
        plugin_name: str,
        payload: dict[str, Any],
        bindings: list[CapabilityBinding] | None = None,
        timeout_seconds: float = 0.0,
        requested_permissions: set[str] | None = None,
    ) -> dict[str, Any]:
        """Execute a plugin with permission validation and timeout.

        Args:
            plugin_name: Name of the registered plugin.
            payload: Input data for the plugin.
            bindings: Capability bindings for permission checks.
            timeout_seconds: Max wall-clock time (0 = no limit).
            requested_permissions: Permissions the execution requires.

        Returns:
            Plugin execution result.

        Raises:
            PermissionError: If required permissions are denied.
            TimeoutError: If execution exceeds timeout_seconds.
            KeyError: If the plugin is not loaded.
            RuntimeError: If the plugin is not RUNNING or lacks execute protocol.
        """
        context = ExecutionContext(
            plugin_name=plugin_name,
            bindings=bindings or [],
            timeout_seconds=timeout_seconds,
        )

        if requested_permissions:
            denied = context.denied_permissions(requested_permissions)
            if denied:
                raise PermissionError(
                    f"Plugin '{plugin_name}' missing permissions: {denied}"
                )

        if timeout_seconds > 0:
            try:
                result = await asyncio.wait_for(
                    self._runtime.execute(plugin_name, payload),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                raise TimeoutError(
                    f"Plugin '{plugin_name}' timed out after {timeout_seconds}s"
                )
        else:
            result = await self._runtime.execute(plugin_name, payload)

        return result
