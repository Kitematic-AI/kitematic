"""MCP Client interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MCPClient(ABC):
    """Interface for MCP client implementations."""

    @abstractmethod
    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call an MCP tool."""
        ...

    @abstractmethod
    async def get_server_info(self) -> dict[str, Any]:
        """Get server information."""
        ...

    @abstractmethod
    async def list_tools(self) -> list[dict[str, Any]]:
        """List available tools."""
        ...
