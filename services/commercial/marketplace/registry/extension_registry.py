"""Extension Registry interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from services.commercial.marketplace.domain.extension_manifest import ExtensionManifest


class ExtensionRegistry(ABC):
    """Abstract interface for extension registry."""

    @abstractmethod
    async def register(self, manifest: ExtensionManifest) -> str:
        """Register an extension manifest. Returns the listing ID."""
        ...

    @abstractmethod
    async def unregister(self, listing_id: str) -> bool:
        """Unregister an extension by listing ID."""
        ...

    @abstractmethod
    async def get(self, listing_id: str) -> ExtensionListing | None:
        """Get an extension listing by ID."""
        ...

    @abstractmethod
    async def list(
        self,
        extension_type: str | None = None,
        publisher_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ExtensionListing]:
        """List extensions with optional filters."""
        ...

    @abstractmethod
    async def update_status(self, listing_id: str, status: str) -> bool:
        """Update the status of a listing."""
        ...


class ExtensionListing:
    """A listing in the marketplace."""

    def __init__(
        self,
        listing_id: str,
        manifest,
        status: str = "DRAFT",
        publisher_id: str = "",
        created_at: str = "",
        updated_at: str = "",
    ):
        self.listing_id = listing_id
        self.manifest = manifest
        self.status = status
        self.publisher_id = publisher_id
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self) -> dict:
        return {
            "listing_id": self.listing_id,
            "manifest": self.manifest,
            "status": self.status,
            "publisher_id": self.publisher_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class InMemoryExtensionRegistry:
    """In-memory implementation of ExtensionRegistry."""

    def __init__(self):
        self._listings: dict[str, dict] = {}

    async def register(self, manifest) -> str:
        import uuid
        listing_id = f"lst-{uuid.uuid4().hex[:12]}"
        from datetime import datetime
        now = datetime.utcnow().isoformat()
        self._listings[listing_id] = {
            "listing_id": listing_id,
            "manifest": manifest,
            "status": "DRAFT",
            "publisher_id": getattr(manifest, "publisher_id", ""),
            "created_at": now,
            "updated_at": now,
        }
        return listing_id

    async def unregister(self, listing_id: str) -> bool:
        if listing_id in self._listings:
            del self._listings[listing_id]
            return True
        return False

    async def get(self, listing_id: str):
        data = self._listings.get(listing_id)
        if not data:
            return None
        return self._listing_from_data(data)

    async def list(
        self,
        extension_type: str | None = None,
        publisher_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ):
        results = []
        for data in self._listings.values():
            if extension_type and data["manifest"].extension_type.value != extension_type:
                continue
            if publisher_id and data["publisher_id"] != publisher_id:
                continue
            if status and data["status"] != status:
                continue
            results.append(self._listing_from_data(data))
        return results[offset : offset + limit]

    async def update_status(self, listing_id: str, status: str) -> bool:
        if listing_id in self._listings:
            self._listings[listing_id]["status"] = status
            from datetime import datetime
            self._listings[listing_id]["updated_at"] = datetime.utcnow().isoformat()
            return True
        return False

    def _listing_from_data(self, data: dict):
        from services.commercial.marketplace.domain.listing_status import ExtensionListingStatus
        return {
            "listing_id": data["listing_id"],
            "manifest": data["manifest"],
            "status": ExtensionListingStatus(data["status"]),
            "publisher_id": data["publisher_id"],
            "created_at": data["created_at"],
            "updated_at": data["updated_at"],
        }
