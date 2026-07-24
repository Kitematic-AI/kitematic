"""Extension loader for marketplace."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExtensionLoadResult:
    """Result of loading an extension."""

    success: bool
    extension: dict = None
    errors: tuple[str, ...] = ()


class ExtensionLoader:
    """Loads and validates extensions for the marketplace."""

    async def load_extension(self, extension_path: str) -> tuple[bool, dict | None, tuple[str, ...]]:
        """Load an extension from a path."""
        try:
            import yaml
            with open(extension_path, "r") as f:
                manifest = yaml.safe_load(f)
            return True, manifest, ()
        except Exception as e:
            return False, None, (str(e),)

    async def validate_extension(self, manifest: dict) -> tuple[bool, tuple[str, ...]]:
        """Validate an extension manifest."""
        errors = []
        required = ["id", "name", "version", "type", "capabilities"]
        for field in required:
            if field not in manifest:
                errors.append(f"Missing required field: {field}")
        return len(errors) == 0, tuple(errors)


class DefaultExtensionLoader(ExtensionLoader):
    """Default implementation of ExtensionLoader."""

    async def load_extension(self, extension_path: str):
        return await super().load_extension(extension_path)

    async def validate_extension(self, manifest: dict):
        return await super().validate_extension(manifest)