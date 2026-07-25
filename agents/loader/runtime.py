"""Plugin Runtime Manager — lifecycle management for loaded plugins.

Loads a PluginManifest entrypoint via importlib, creates an instance,
runs lifecycle hooks, and tracks running plugin instances.
"""

from __future__ import annotations

import importlib
import logging
from enum import Enum
from typing import Any

from core.contracts.plugin import (
    PluginExecutableProtocol,
    PluginHealthProtocol,
    PluginLifecycleProtocol,
)
from core.domain.plugin import PluginManifest

logger = logging.getLogger("kitematic.loader.runtime")


class PluginRuntimeState(Enum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


class PluginRuntimeManager:
    """Manages plugin lifecycle: load, execute, health, shutdown."""

    def __init__(self) -> None:
        self._plugins: dict[str, Any] = {}
        self._states: dict[str, PluginRuntimeState] = {}

    # ── Load ──────────────────────────────────────────────────────────────────

    async def load(self, manifest: PluginManifest) -> None:
        """Import, instantiate, verify, initialize, and register a plugin.

        Args:
            manifest: Validated plugin manifest with entrypoint spec.

        Raises:
            ValueError: If the plugin class is missing or does not conform
                to PluginLifecycleProtocol.
        """
        name = manifest.name
        try:
            module = importlib.import_module(manifest.entrypoint["module"])
        except (ImportError, ModuleNotFoundError) as exc:
            self._states[name] = PluginRuntimeState.FAILED
            raise ValueError(
                f"Plugin '{name}': cannot import module "
                f"'{manifest.entrypoint['module']}': {exc}"
            ) from exc

        try:
            plugin_cls = getattr(module, manifest.entrypoint["class"])
        except AttributeError as exc:
            self._states[name] = PluginRuntimeState.FAILED
            raise ValueError(
                f"Plugin '{name}': class '{manifest.entrypoint['class']}' "
                f"not found in module '{manifest.entrypoint['module']}'"
            ) from exc

        plugin = plugin_cls()

        if not isinstance(plugin, PluginLifecycleProtocol):
            self._states[name] = PluginRuntimeState.FAILED
            raise ValueError(
                f"Plugin '{name}' does not implement PluginLifecycleProtocol. "
                f"Missing one or more of: initialize, shutdown."
            )

        await plugin.initialize()

        self._plugins[name] = plugin
        self._states[name] = PluginRuntimeState.RUNNING
        logger.info("Plugin '%s' loaded and running", name)

    # ── Execute ───────────────────────────────────────────────────────────────

    async def execute(
        self,
        name: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Dispatch a payload to a running plugin.

        Args:
            name: Registered plugin name.
            payload: Input data for the plugin.

        Returns:
            Plugin execution result.

        Raises:
            KeyError: If the plugin is not registered.
            RuntimeError: If the plugin is not in RUNNING state.
        """
        if name not in self._plugins:
            raise KeyError(f"Plugin '{name}' is not loaded")

        if self._states.get(name) != PluginRuntimeState.RUNNING:
            raise RuntimeError(f"Plugin '{name}' is not RUNNING (state={self._states[name].value})")

        plugin = self._plugins[name]

        if not isinstance(plugin, PluginExecutableProtocol):
            raise RuntimeError(
                f"Plugin '{name}' does not implement PluginExecutableProtocol"
            )

        return await plugin.execute(payload)

    # ── Health ────────────────────────────────────────────────────────────────

    async def health_check(self) -> dict[str, bool]:
        """Run health check on all loaded plugins.

        Returns:
            Dict mapping plugin name to healthy (True/False).
        """
        result: dict[str, bool] = {}
        for name, plugin in self._plugins.items():
            if isinstance(plugin, PluginHealthProtocol):
                try:
                    result[name] = await plugin.health_check()
                except Exception:
                    result[name] = False
            else:
                result[name] = self._states.get(name) == PluginRuntimeState.RUNNING
        return result

    # ── Shutdown ──────────────────────────────────────────────────────────────

    async def shutdown_all(self) -> None:
        """Shut down all running plugins gracefully."""
        for name, plugin in self._plugins.items():
            if isinstance(plugin, PluginLifecycleProtocol):
                try:
                    await plugin.shutdown()
                except Exception:
                    logger.exception("Plugin '%s' shutdown failed", name)
            self._states[name] = PluginRuntimeState.STOPPED
        logger.info("All plugins shut down")

    # ── State ─────────────────────────────────────────────────────────────────

    def state(self, name: str) -> PluginRuntimeState | None:
        """Return the current state of a plugin.

        Args:
            name: Registered plugin name.

        Returns:
            Current PluginRuntimeState, or None if not found.
        """
        return self._states.get(name)

    @property
    def loaded_count(self) -> int:
        """Number of loaded plugins."""
        return len(self._plugins)

    @property
    def running_count(self) -> int:
        """Number of plugins in RUNNING state."""
        return sum(
            1 for s in self._states.values() if s == PluginRuntimeState.RUNNING
        )
