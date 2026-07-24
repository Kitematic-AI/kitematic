"""MCP Tool definition."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MCPToolDefinition:
    """Definition of an MCP tool."""

    name: str
    description: str = ""
    input_schema: dict = None
    output_schema: dict = None
    tags: tuple[str, ...] = ()

    def __post_init__(self):
        if self.input_schema is None:
            object.__setattr__(self, "input_schema", {})
        if self.output_schema is None:
            object.__setattr__(self, "output_schema", {})