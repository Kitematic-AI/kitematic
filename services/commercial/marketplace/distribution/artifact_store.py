"""Artifact store for marketplace distribution."""

from __future__ import annotations

from typing import Any

from services.commercial.marketplace.domain.extension_manifest import ExtensionManifest


class InMemoryArtifactStore:
    """In-memory artifact store for extension packages."""

    def __init__(self):
        self._artifacts: dict[str, bytes] = {}
        self._metadata: dict[str, dict] = {}

    async def store(self, manifest: "ExtensionManifest", artifact_data: bytes) -> str:
        """Store an artifact and return its ID."""
        import hashlib
        artifact_id = hashlib.sha256(artifact_data).hexdigest()[:16]
        self._artifacts[artifact_id] = artifact_data
        self._metadata[artifact_id] = {
            "manifest_id": manifest.extension_id,
            "version": manifest.version,
            "checksum": hashlib.sha256(artifact_data).hexdigest(),
        }
        return artifact_id

    async def retrieve(self, artifact_id: str) -> bytes | None:
        return self._artifacts.get(artifact_id)

    async def delete(self, artifact_id: str) -> bool:
        if artifact_id in self._artifacts:
            del self._artifacts[artifact_id]
            self._metadata.pop(artifact_id, None)
            return True
        return False

    async def get_metadata(self, artifact_id: str) -> dict | None:
        return self._metadata.get(artifact_id)