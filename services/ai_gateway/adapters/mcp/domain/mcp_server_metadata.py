"""MCP Server metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MCPServerMetadata:
    """Metadata for an MCP server."""

    server_id: str
    name: str
    version: str = "1.0"
    transport: str = "stdio"
    capabilities: dict = field(default_factory=dict)