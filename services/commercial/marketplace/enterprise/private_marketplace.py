"""Private marketplace for enterprise deployments."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class PrivateMarketplaceConfig:
    """Configuration for a private marketplace."""

    marketplace_id: str
    name: str
    owner_organization: str
    allowed_publishers: tuple[str, ...] = ()
    allowed_extensions: tuple[str, ...] = ()
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class PrivateMarketplace:
    """Private marketplace for enterprise deployments."""

    def __init__(self, config):
        self._config = config
        self._extensions: dict[str, dict] = {}

    @property
    def config(self):
        return self._config

    async def add_extension(self, listing) -> str:
        """Add an extension to the private marketplace."""
        import uuid
        listing_id = f"prv-{uuid.uuid4().hex[:12]}"
        self._extensions[listing_id] = {
            "listing": listing,
            "added_at": datetime.utcnow().isoformat(),
        }
        return listing_id

    async def remove_extension(self, listing_id: str) -> bool:
        if listing_id in self._extensions:
            del self._extensions[listing_id]
            return True
        return False

    async def list_extensions(self) -> list:
        return list(self._extensions.values())

    async def get_extension(self, listing_id: str):
        return self._extensions.get(listing_id)
