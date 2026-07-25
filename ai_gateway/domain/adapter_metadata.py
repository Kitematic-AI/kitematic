"""Adapter metadata domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ai_gateway.domain.adapter_status import AdapterStatus


@dataclass(frozen=True)
class AdapterMetadata:
    """Immutable metadata for an adapter."""

    adapter_id: str
    name: str
    version: str
    capabilities: tuple[str, ...] = ()
    provider: str = ""
    status: AdapterStatus = AdapterStatus.UNKNOWN
    config_schema: dict[str, Any] = field(default_factory=dict)
    description: str = ""
