"""AI Gateway interfaces package."""

from __future__ import annotations

from .adapter import RuntimeAdapter, CapabilityId, CapabilitySet, GatewayRequest, GatewayResponse, AdapterHealth
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