"""AI Gateway usage record model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


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
    metadata: dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})