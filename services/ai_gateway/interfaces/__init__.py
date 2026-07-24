"""AI Gateway interfaces package."""

from __future__ import annotations

from .adapter import (
    AdapterHealth,
    CapabilityId,
    CapabilitySet,
    GatewayRequest,
    GatewayResponse,
    RuntimeAdapter,
)
from .gateway import Gateway

__all__ = [
    "RuntimeAdapter",
    "Gateway",
    "CapabilityId",
    "CapabilitySet",
    "GatewayRequest",
    "GatewayResponse",
    "AdapterHealth",
]
