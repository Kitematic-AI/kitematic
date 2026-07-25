"""Adapter Registry — interface and base implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.contracts.adapter import RuntimeAdapter


class AdapterRegistry(ABC):
    """Abstract interface for adapter registry."""

    @abstractmethod
    def register(self, adapter: RuntimeAdapter) -> None:
        """Register an adapter."""
        ...

    @abstractmethod
    def unregister(self, adapter_id: str) -> None:
        """Unregister an adapter by ID."""
        ...

    @abstractmethod
    def get(self, adapter_id: str) -> RuntimeAdapter | None:
        """Get an adapter by ID."""
        ...

    @abstractmethod
    def list(self) -> list[RuntimeAdapter]:
        """List all registered adapters."""
        ...


class InMemoryAdapterRegistry:
    """In-memory implementation of AdapterRegistry."""

    def __init__(self) -> None:
        self._adapters: dict[str, RuntimeAdapter] = {}

    def register(self, adapter: RuntimeAdapter) -> None:
        adapter_id = getattr(adapter, "metadata", {}).get("adapter_id", "")
        if not adapter_id:
            raise ValueError("Adapter must have metadata with adapter_id")
        self._adapters[adapter_id] = adapter

    def unregister(self, adapter_id: str) -> None:
        self._adapters.pop(adapter_id, None)

    def get(self, adapter_id: str) -> RuntimeAdapter | None:
        return self._adapters.get(adapter_id)

    def list(self) -> list[RuntimeAdapter]:
        return list(self._adapters.values())
