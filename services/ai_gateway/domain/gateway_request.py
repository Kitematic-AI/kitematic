"""AI Gateway domain request model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class GatewayRequest:
    """Request sent to the AI Gateway."""
    
    capability: str
    payload: dict
    metadata: dict = field(default_factory=dict)
    tenant_id: str = ""
    trace_id: str = ""
    request_id: str = ""