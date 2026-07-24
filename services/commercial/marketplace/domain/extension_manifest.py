"""Extension manifest model for marketplace."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ExtensionManifest:
    """Complete manifest for a marketplace extension."""

    extension_id: str
    name: str
    version: str
    publisher_id: str
    description: str = ""
    readme: str = ""
    tags: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    allowed_models: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    min_runtime_version: str = "1.0.0"
    max_runtime_version: str | None = None
    icon_url: str = ""
    homepage_url: str = ""
    repository_url: str = ""
    license: str = "MIT"
    keywords: tuple[str, ...] = ()
    maintainers: tuple[str, ...] = ()
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        """Validate manifest integrity."""
        from services.commercial.marketplace.model.invariants import MARKETPLACE_INVARIANTS

        errors = []

        # Validate extension_id
        errors.extend(self.validate_extension_id(self.extension_id))

        # Validate version format
        import re
        if not re.match(r"^\d+\.\d+\.\d+(-[a-z0-9\.\-]+)?(\+[a-z0-9\.\-]+)?$", self.version):
            errors.append(f"Invalid version format: {self.version}")

        # Validate capabilities
        cap_errors = MARKETPLACE_INVARIANTS.validate_capabilities(self.capabilities)
        errors.extend(cap_errors)

        return errors

    @staticmethod
    def validate_extension_id(extension_id: str) -> list[str]:
        """Validate extension ID format."""
        import re
        errors = []

        if len(extension_id) < 3:
            errors.append("Extension ID must be at least 3 characters")
        if len(extension_id) > 64:
            errors.append("Extension ID too long (max 64 chars)")

        if not re.match(r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$|^[a-z0-9]$", extension_id):
            errors.append("Extension ID must be lowercase alphanumeric with hyphens")

        return errors


class ExtensionManifestValidator:
    """Validates extension manifests against marketplace invariants."""

    def __init__(self):
        from services.commercial.marketplace.model.invariants import MARKETPLACE_INVARIANTS
        self.invariants = MARKETPLACE_INVARIANTS

    def validate(self, manifest) -> list[str]:
        """Validate an extension manifest."""
        errors = []

        # Extension ID
        errors.extend(manifest.validate_extension_id(manifest.extension_id))

        # Version
        import re
        if not re.match(r"^\d+\.\d+\.\d+(-[a-z0-9\.\-]+)?(\+[a-z0-9\.\-]+)?$", manifest.version):
            errors.append(f"Invalid version format: {manifest.version}")

        # Capabilities
        cap_errors = self.validate_capabilities(manifest.capabilities)
        return errors

    def validate_capabilities(self, capabilities: tuple[str, ...]) -> list[str]:
        """Validate capability list against invariants."""
        return self.invariants.validate_capabilities(capabilities)
