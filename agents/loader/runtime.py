"""Plugin Runtime Manager — lifecycle management for loaded plugins.

Loads a PluginManifest entrypoint via importlib, creates an instance,
runs lifecycle hooks, and tracks running plugin instances.

Optionally persists state via a PluginRuntimeStore.
"""

from __future__ import annotations

import importlib
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from core.contracts.plugin import (
    PluginExecutableProtocol,
    PluginHealthProtocol,
    PluginLifecycleProtocol,
)
from core.contracts.plugin_runtime import PluginRuntimeStore
from core.domain.plugin import PluginManifest
from core.domain.plugin_runtime import PluginRuntimeRecord
from core.domain.runtime_event import RuntimeEvent

logger = logging.getLogger("kitematic.loader.runtime")


class PluginRuntimeState(Enum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


EVENT_LOADED = "loaded"
EVENT_STARTED = "started"
EVENT_FAILED = "failed"
EVENT_STOPPED = "stopped"
EVENT_HEALTH_OK = "health_ok"
EVENT_HEALTH_FAIL = "health_fail"


class PluginRuntimeManager:
    """Manages plugin lifecycle: load, execute, health, shutdown.

    Args:
        store: Optional persistence backend for runtime records.
    """

    def __init__(self, store: PluginRuntimeStore | None = None) -> None:
        self._plugins: dict[str, Any] = {}
        self._states: dict[str, PluginRuntimeState] = {}
        self._versions: dict[str, str] = {}
        self._store = store
        self._events: list[RuntimeEvent] = []

    # ── Persistence helpers ───────────────────────────────────────────────────

    async def _persist(
        self,
        name: str,
        state: PluginRuntimeState,
        error: str | None = None,
    ) -> None:
        if self._store is None:
            return
        version = self._versions.get(name, "")
        record = PluginRuntimeRecord(
            name=name,
            version=version,
            state=state,
            loaded_at=datetime.now(timezone.utc) if state == PluginRuntimeState.RUNNING else None,
            last_health_check=(
                datetime.now(timezone.utc) if state == PluginRuntimeState.RUNNING else None
            ),
            error=error,
        )
        await self._store.save(record)

    def _emit(self, plugin_name: str, event_type: str, **metadata: Any) -> None:
        event = RuntimeEvent(
            plugin_name=plugin_name,
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or None,
        )
        self._events.append(event)

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
        self._versions[name] = manifest.version
        try:
            module = importlib.import_module(manifest.entrypoint["module"])
        except (ImportError, ModuleNotFoundError) as exc:
            self._states[name] = PluginRuntimeState.FAILED
            await self._persist(name, PluginRuntimeState.FAILED, str(exc))
            self._emit(name, EVENT_FAILED, error=str(exc))
            raise ValueError(
                f"Plugin '{name}': cannot import module "
                f"'{manifest.entrypoint['module']}': {exc}"
            ) from exc

        try:
            plugin_cls = getattr(module, manifest.entrypoint["class"])
        except AttributeError as exc:
            self._states[name] = PluginRuntimeState.FAILED
            await self._persist(name, PluginRuntimeState.FAILED, str(exc))
            self._emit(name, EVENT_FAILED, error=str(exc))
            raise ValueError(
                f"Plugin '{name}': class '{manifest.entrypoint['class']}' "
                f"not found in module '{manifest.entrypoint['module']}'"
            ) from exc

        plugin = plugin_cls()

        if not isinstance(plugin, PluginLifecycleProtocol):
            self._states[name] = PluginRuntimeState.FAILED
            await self._persist(name, PluginRuntimeState.FAILED,
                                "missing PluginLifecycleProtocol")
            self._emit(name, EVENT_FAILED, error="missing PluginLifecycleProtocol")
            raise ValueError(
                f"Plugin '{name}' does not implement PluginLifecycleProtocol. "
                f"Missing one or more of: initialize, shutdown."
            )

        self._emit(name, EVENT_LOADED, version=manifest.version)

        try:
            await plugin.initialize()
        except Exception as exc:
            self._states[name] = PluginRuntimeState.FAILED
            await self._persist(name, PluginRuntimeState.FAILED, str(exc))
            self._emit(name, EVENT_FAILED, error=str(exc))
            raise

        self._plugins[name] = plugin
        self._states[name] = PluginRuntimeState.RUNNING
        await self._persist(name, PluginRuntimeState.RUNNING)
        self._emit(name, EVENT_STARTED)
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
                    healthy = await plugin.health_check()
                    result[name] = healthy
                    self._emit(
                        name,
                        EVENT_HEALTH_OK if healthy else EVENT_HEALTH_FAIL,
                    )
                except Exception:
                    result[name] = False
                    self._emit(name, EVENT_HEALTH_FAIL, error="exception")
            else:
                result[name] = self._states.get(name) == PluginRuntimeState.RUNNING

            if self._store is not None and name in self._states:
                record = PluginRuntimeRecord(
                    name=name,
                    version="",
                    state=self._states[name],
                    last_health_check=datetime.now(timezone.utc),
                )
                await self._store.save(record)
        return result

    # ── Shutdown ──────────────────────────────────────────────────────────────

    async def shutdown(self, name: str) -> None:
        """Shut down a single plugin gracefully.

        Args:
            name: Registered plugin name.
        """
        plugin = self._plugins.get(name)
        if plugin is None:
            return
        if isinstance(plugin, PluginLifecycleProtocol):
            try:
                await plugin.shutdown()
            except Exception:
                logger.exception("Plugin '%s' shutdown failed", name)
        self._states[name] = PluginRuntimeState.STOPPED
        await self._persist(name, PluginRuntimeState.STOPPED)
        self._emit(name, EVENT_STOPPED)
        logger.info("Plugin '%s' shut down", name)

    async def shutdown_all(self) -> None:
        """Shut down all running plugins gracefully."""
        for name in list(self._plugins):
            await self.shutdown(name)
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

    @property
    def events(self) -> list[RuntimeEvent]:
        """Return emitted events for audit/observability."""
        return list(self._events)
