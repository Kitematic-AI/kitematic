"""Tool registry — centralized tool discovery and validation.

Maps tool IDs to MCP servers. Every tool MUST be registered before access.
Unknown tools are rejected at the gateway boundary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


class ToolNotFoundError(Exception):
    """Raised when a tool is not found in the registry."""

    def __init__(self, tool_id: str):
        self.tool_id = tool_id
        super().__init__(f"Tool not found: {tool_id}")


class ToolAlreadyRegisteredError(Exception):
    """Raised when registering a tool that already exists."""

    def __init__(self, tool_id: str):
        self.tool_id = tool_id
        super().__init__(f"Tool already registered: {tool_id}")


class ToolCapabilityMismatchError(Exception):
    """Raised when agent lacks required capabilities for a tool."""

    def __init__(self, tool_id: str, required: frozenset[str], provided: frozenset[str]):
        self.tool_id = tool_id
        self.required = required
        self.provided = provided
        super().__init__(
            f"Tool '{tool_id}' requires capabilities {sorted(required)}, "
            f"agent has {sorted(provided)}"
        )


@dataclass(frozen=True)
class ToolDefinition:
    """Definition of a registered tool.

    Frozen to prevent modification during execution.
    Maps a tool ID to its MCP server and requirements.
    """

    tool_id: str
    mcp_server: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    required_capabilities: frozenset[str] = field(default_factory=frozenset)
    tags: frozenset[str] = field(default_factory=frozenset)
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        """Validate tool definition integrity."""
        errors: list[str] = []
        if not self.tool_id:
            errors.append("tool_id is required")
        if not self.mcp_server:
            errors.append("mcp_server is required")
        return errors

    @property
    def is_valid(self) -> bool:
        return len(self.validate()) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "mcp_server": self.mcp_server,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "required_capabilities": sorted(self.required_capabilities),
            "tags": sorted(self.tags),
            "metadata": self.metadata,
        }


class ToolRegistry:
    """Centralized tool registry — maps tool IDs to MCP servers.

    Responsibilities:
      - Register tools with their MCP server mapping
      - Look up tools by ID
      - Match tools by pattern (e.g. "mcp.database.*")
      - Validate tool existence before gateway access

    Does NOT:
      - Execute tools (ToolGateway role)
      - Make policy decisions (Policy Engine role)
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool."""
        if not tool.is_valid:
            raise ValueError(f"Invalid tool definition: {tool.validate()}")
        if tool.tool_id in self._tools:
            raise ToolAlreadyRegisteredError(tool.tool_id)
        self._tools[tool.tool_id] = tool

    def unregister(self, tool_id: str) -> None:
        """Unregister a tool."""
        if tool_id not in self._tools:
            raise ToolNotFoundError(tool_id)
        del self._tools[tool_id]

    def get(self, tool_id: str) -> ToolDefinition | None:
        """Get a registered tool by ID."""
        return self._tools.get(tool_id)

    def is_registered(self, tool_id: str) -> bool:
        """Check if a tool is registered."""
        return tool_id in self._tools

    def match_pattern(self, pattern: str) -> list[ToolDefinition]:
        """Match tools by glob pattern (e.g. 'mcp.database.*').

        Supports:
          - Exact match: "mcp.database.query"
          - Single wildcard: "mcp.database.*"
          - Multi-level: "mcp.*"
        """
        regex = re.escape(pattern).replace(r"\.\*", r"\..*")
        regex = f"^{regex}$"
        return [t for t in self._tools.values() if re.match(regex, t.tool_id)]

    def list_tools(self) -> list[ToolDefinition]:
        """List all registered tools."""
        return list(self._tools.values())

    def validate_access(
        self, tool_id: str, agent_capabilities: frozenset[str] | None = None
    ) -> ToolDefinition:
        """Validate tool exists and agent has required capabilities.

        Returns ToolDefinition if valid.
        Raises ToolNotFoundError or ToolCapabilityMismatchError.
        """
        tool = self._tools.get(tool_id)
        if tool is None:
            raise ToolNotFoundError(tool_id)

        if agent_capabilities is not None and tool.required_capabilities:
            if not tool.required_capabilities.issubset(agent_capabilities):
                raise ToolCapabilityMismatchError(
                    tool_id=tool_id,
                    required=tool.required_capabilities,
                    provided=agent_capabilities,
                )

        return tool

    @property
    def count(self) -> int:
        """Number of registered tools."""
        return len(self._tools)

    def to_dict(self) -> dict[str, Any]:
        """Serialize registry state."""
        return {
            "tool_count": self.count,
            "tools": {tid: t.to_dict() for tid, t in self._tools.items()},
        }
