"""Default extension loader."""

from __future__ import annotations

from .extension_loader import ExtensionLoader


class DefaultExtensionLoader(ExtensionLoader):
    """Default implementation of ExtensionLoader."""

    async def load_extension(self, extension_path: str):
        return await super().load_extension(extension_path)

    async def validate_extension(self, manifest: dict):
        return await super().validate_extension(manifest)