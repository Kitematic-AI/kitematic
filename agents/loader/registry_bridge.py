"""Registry bridge — wires a plugin through policy evaluation into the registry + kernel.

Flow:
  PluginManifest → PolicyEngine.evaluate_with_capabilities() → Registry → ToolRegistry

The bridge is the only component that connects agents/loader to kernel and control_plane.
It does NOT import kernel/ or control_plane/ directly — it accepts interface objects.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from core.domain.plugin import PluginManifest

logger = logging.getLogger("kitematic.loader.bridge")


class CapabilityStore(Protocol):
    """Protocol for registering plugin capabilities.

    Implemented by control_plane/policy/engine or a dedicated capability registry.
    """

    async def add_capabilities(
        self,
        plugin_name: str,
        capabilities: list[dict[str, Any]],
    ) -> None:
        ...

    async def remove_capabilities(self, plugin_name: str) -> None:
        ...


class ToolRegistry(Protocol):
    """Protocol for registering plugin entrypoints as tools.

    Implemented by kernel/resources/tool_registry.
    """

    def register_tool(self, tool_id: str, entrypoint: dict[str, str]) -> None:
        ...

    def unregister_tool(self, tool_id: str) -> None:
        ...


class PolicyEvaluator(Protocol):
    """Protocol for evaluating plugin capabilities against policy.

    Implemented by control_plane/policy/engine.
    """

    async def evaluate_capabilities(
        self,
        capabilities: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
    ) -> bool:
        ...


@dataclass
class RegistrationResult:
    success: bool
    plugin_name: str
    errors: list[str] = field(default_factory=list)


async def register(
    manifest: PluginManifest,
    capability_store: CapabilityStore,
    tool_registry: ToolRegistry,
    policy_evaluator: PolicyEvaluator | None = None,
) -> RegistrationResult:
    """Register a plugin through policy evaluation into the system.

    Args:
        manifest: Validated plugin manifest.
        capability_store: Registry to store capabilities.
        tool_registry: Kernel tool registry for plugin entrypoints.
        policy_evaluator: Optional policy engine (skips evaluation if None).

    Returns:
        RegistrationResult with success status and any errors.
    """
    if policy_evaluator is not None:
        ctx = {"plugin_name": manifest.name, "plugin_type": manifest.plugin_type.value}
        allowed = await policy_evaluator.evaluate_capabilities(
            manifest.capabilities, context=ctx,
        )
        if not allowed:
            return RegistrationResult(
                success=False,
                plugin_name=manifest.name,
                errors=[f"Plugin '{manifest.name}' capabilities rejected by policy"],
            )

    await capability_store.add_capabilities(manifest.name, manifest.capabilities)

    tool_registry.register_tool(manifest.name, manifest.entrypoint)

    logger.info(
        "Registered plugin '%s' v%s (%s capabilities)",
        manifest.name,
        manifest.version,
        len(manifest.capabilities),
    )
    return RegistrationResult(success=True, plugin_name=manifest.name)


async def unregister(
    manifest_name: str,
    capability_store: CapabilityStore,
    tool_registry: ToolRegistry,
) -> None:
    """Remove a plugin from the system.

    Args:
        manifest_name: Name of the plugin to unregister.
        capability_store: Registry to remove capabilities from.
        tool_registry: Kernel tool registry to remove entrypoint from.
    """
    await capability_store.remove_capabilities(manifest_name)
    tool_registry.unregister_tool(manifest_name)
    logger.info("Unregistered plugin '%s'", manifest_name)
