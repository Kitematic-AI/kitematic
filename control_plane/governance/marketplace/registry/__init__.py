"""Marketplace registry package."""

from __future__ import annotations

from .extension_registry import ExtensionRegistry, InMemoryExtensionRegistry

__all__ = [
    "ExtensionRegistry",
    "InMemoryExtensionRegistry",
]
