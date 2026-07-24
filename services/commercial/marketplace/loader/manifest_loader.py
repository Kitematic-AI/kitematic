"""Manifest loader for marketplace extensions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ManifestLoadResult:
    """Result of loading a manifest."""

    success: bool
    manifest: dict = None
    errors: tuple[str, ...] = ()


class ManifestLoader:
    """Loads and parses extension manifests."""

    async def load_manifest(self, manifest_path: str) -> tuple[bool, dict | None, tuple[str, ...]]:
        """Load a manifest from a file path."""
        try:
            import yaml
            with open(manifest_path, "r") as f:
                manifest = yaml.safe_load(f)
            return True, manifest, ()
        except Exception as e:
            return False, None, (str(e),)

    async def load_manifest(self, manifest_data: dict) -> tuple[bool, dict | None, tuple[str, ...]]:
        """Load a manifest from a dictionary."""
        return True, manifest_data, ()


class DefaultManifestLoader(ManifestLoader):
    """Default manifest loader with standard validation."""

    async def validate_manifest(self, manifest: dict) -> tuple[bool, tuple[str, ...]]:
        """Validate a manifest structure."""
        errors = []
        required = ["id", "name", "version", "type"]
        for field in required:
            if field not in manifest:
                errors.append(f"Missing required field: {field}")
        return len(errors) == 0, tuple(errors)