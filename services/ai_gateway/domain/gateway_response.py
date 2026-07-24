"""AI Gateway response and usage models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class GatewayResponse:
    """Response from the AI Gateway."""
    
    success: bool
    result: dict | None = None
    error: str | None = None
    usage: "UsageRecord | None" = None
    trace: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: str(datetime.utcnow()))


@dataclass(frozen=True)
class UsageRecord:
    """Record of resource usage for a gateway request."""
    
    capability: str
    adapter_id: str
    timestamp: str
    input_units: int = 0
    output_units: int = 0
    cost: float | None = None
    provider_id: str = ""
    tenant_id: str = ""
    trace_id: str = ""
    request_id: str = ""
    metadata: dict = field(default_factory=dict)