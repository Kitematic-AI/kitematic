"""Plugin lifecycle orchestration — connects loader to runtime.

Coordinates discovery, registration, and runtime lifecycle into a single
activation/deactivation flow.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from agents.loader.registry_bridge import (
    CapabilityStore,
    PolicyEvaluator,
    ToolRegistry,
    register,
    unregister,
)
from agents.loader.runtime import PluginRuntimeManager
from core.domain.plugin import PluginManifest

logger = logging.getLogger("kitematic.loader.lifecycle")


@dataclass
class ActivationResult:
    success: bool
    plugin_name: str
    errors: list[str] = field(default_factory=list)


class PluginLifecycleManager:
    """Orchestrates the full plugin lifecycle.

    Flow:
        validate → register (policy + capabilities + tools) → load runtime → RUNNING

    Reverse:
        shutdown runtime → unregister tools → remove capabilities → REMOVED
    """

    def __init__(
        self,
        runtime: PluginRuntimeManager,
        capability_store: CapabilityStore,
        tool_registry: ToolRegistry,
        policy_evaluator: PolicyEvaluator | None = None,
    ) -> None:
        self._runtime = runtime
        self._capability_store = capability_store
        self._tool_registry = tool_registry
        self._policy_evaluator = policy_evaluator

    async def activate(self, manifest: PluginManifest) -> ActivationResult:
        """Validate, register, and load a plugin.

        Args:
            manifest: Validated plugin manifest.

        Returns:
            ActivationResult with success status and any errors.
        """
        # 1. Register through policy + capability store + tool registry
        reg_result = await register(
            manifest,
            self._capability_store,
            self._tool_registry,
            self._policy_evaluator,
        )
        if not reg_result.success:
            return ActivationResult(
                success=False,
                plugin_name=manifest.name,
                errors=reg_result.errors,
            )

        # 2. Load into runtime (importlib + initialize)
        try:
            await self._runtime.load(manifest)
        except Exception as exc:
            await unregister(
                manifest.name,
                self._capability_store,
                self._tool_registry,
            )
            return ActivationResult(
                success=False,
                plugin_name=manifest.name,
                errors=[str(exc)],
            )

        logger.info(
            "Plugin '%s' v%s activated",
            manifest.name,
            manifest.version,
        )
        return ActivationResult(success=True, plugin_name=manifest.name)

    async def deactivate(self, name: str) -> None:
        """Shut down and unregister a plugin.

        Args:
            name: Plugin name to deactivate.
        """
        # 1. Shutdown runtime first
        await self._runtime.shutdown(name)

        # 2. Unregister from capability store and tool registry
        await unregister(name, self._capability_store, self._tool_registry)

        logger.info("Plugin '%s' deactivated", name)
