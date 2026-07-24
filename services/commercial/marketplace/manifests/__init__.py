"""Marketplace manifests package."""

from __future__ import annotations

from services.core.domain.capability_catalog import CapabilityCatalog

from ..domain.extension_manifest import ExtensionManifest, ExtensionManifestValidator

__all__ = [
    "ExtensionManifest",
    "ExtensionManifestValidator",
    "CapabilityCatalog",
]
