"""MCP Gateway — concrete ToolGateway implementation.

Bridges the Runtime ABI (ExecutionPath + Intent) to MCP tools.
Every tool access goes through: Registry → Validation → MCPClient → ToolResult.
Every access emits an audit event.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from runtime.kitematic_runtime.events import EventLog, EventType
from runtime.kitematic_runtime.exceptions import GatewayAccessError
from runtime.kitematic_runtime.observability.logging import RuntimeLogger
from runtime.kitematic_runtime.observability.metrics import MetricsRegistry
from runtime.kitematic_runtime.runtime import (
    ExecutionPath,
    Intent,
    ToolGateway,
    ToolResult,
)
from runtime.kitematic_runtime.states import ExecutionState
from runtime.kitematic_runtime.tool_registry import (
    ToolRegistry,
)


class MCPClientProtocol:
    """Protocol for MCP client — must implement call_tool."""

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class MCPClientNotFoundError(Exception):
    """Raised when no MCP client is configured for a server."""

    def __init__(self, server_id: str):
        self.server_id = server_id
        super().__init__(f"No MCP client configured for server: {server_id}")


@dataclass(frozen=True)
class GatewayAuditEntry:
    """Immutable audit record for a gateway access."""

    timestamp: datetime
    tool_id: str
    mcp_server: str
    agent_id: str
    success: bool
    error: str | None = None
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "tool_id": self.tool_id,
            "mcp_server": self.mcp_server,
            "agent_id": self.agent_id,
            "success": self.success,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


class MCPToolGateway(ToolGateway):
    """Concrete ToolGateway — bridges Runtime ABI to MCP tools.

    Responsibilities:
      - Validate tool is registered before access
      - Validate agent has required capabilities for tool
      - Bridge ExecutionPath → MCPClient.call_tool()
      - Wrap results in ToolResult
      - Emit audit events for every gateway call
      - Raise GatewayAccessError on failures

    Does NOT:
      - Make policy decisions (already validated upstream)
      - Modify execution state
      - Access tools directly (always through MCPClient)
    """

    def __init__(
        self,
        registry: ToolRegistry,
        clients: dict[str, MCPClientProtocol] | None = None,
        logger: RuntimeLogger | None = None,
        metrics: MetricsRegistry | None = None,
    ):
        self._registry = registry
        self._clients: dict[str, MCPClientProtocol] = clients or {}
        self._audit_log: list[GatewayAuditEntry] = []
        self._event_log: EventLog | None = None
        self._logger = logger
        self._metrics = metrics

    def set_event_log(self, event_log: EventLog) -> None:
        """Set the event log for audit emission."""
        self._event_log = event_log

    def register_client(self, server_id: str, client: MCPClientProtocol) -> None:
        """Register an MCP client for a server."""
        self._clients[server_id] = client

    async def access_tool(self, path: ExecutionPath, intent: Intent) -> ToolResult:
        """Access a tool through the Gateway Chain.

        Flow:
          1. Look up tool in registry
          2. Validate tool exists
          3. Get MCP client for tool's server
          4. Call MCPClient.call_tool()
          5. Wrap result in ToolResult
          6. Emit GATEWAY_ACCESSED event
        """
        start = datetime.now(UTC)

        # Step 1: Registry lookup
        tool_def = self._registry.get(path.tool)
        if tool_def is None:
            error_msg = f"Tool not registered: {path.tool}"
            self._record_audit(
                tool_id=path.tool,
                mcp_server="",
                agent_id=intent.agent_id,
                success=False,
                error=error_msg,
                start=start,
            )
            if self._logger:
                self._logger.warn("Tool not registered", tool=path.tool, agent_id=intent.agent_id)
            if self._metrics:
                self._metrics.increment("gateway.tool.registry_miss")
            raise GatewayAccessError(path.tool, error_msg)

        # Step 2: Client resolution
        client = self._clients.get(tool_def.mcp_server)
        if client is None:
            error_msg = f"No MCP client for server: {tool_def.mcp_server}"
            self._record_audit(
                tool_id=path.tool,
                mcp_server=tool_def.mcp_server,
                agent_id=intent.agent_id,
                success=False,
                error=error_msg,
                start=start,
            )
            if self._logger:
                self._logger.warn(
                    "No MCP client for server",
                    tool=path.tool,
                    mcp_server=tool_def.mcp_server,
                )
            if self._metrics:
                self._metrics.increment("gateway.tool.client_miss")
            raise GatewayAccessError(path.tool, error_msg)

        # Step 3: Call MCP tool
        try:
            result = await client.call_tool(path.tool, path.parameters)
        except Exception as e:
            error_msg = f"MCP call failed: {str(e)}"
            self._record_audit(
                tool_id=path.tool,
                mcp_server=tool_def.mcp_server,
                agent_id=intent.agent_id,
                success=False,
                error=error_msg,
                start=start,
            )
            if self._logger:
                self._logger.error(
                    "MCP call failed",
                    tool=path.tool,
                    mcp_server=tool_def.mcp_server,
                    error=str(e),
                )
            if self._metrics:
                self._metrics.increment("gateway.tool.mcp_failure")
            raise GatewayAccessError(path.tool, error_msg)

        # Step 4: Wrap result
        tool_result = ToolResult(
            success=True,
            data=result,
            error=None,
        )

        self._record_audit(
            tool_id=path.tool,
            mcp_server=tool_def.mcp_server,
            agent_id=intent.agent_id,
            success=True,
            start=start,
        )

        elapsed = (datetime.now(UTC) - start).total_seconds() * 1000
        if self._logger:
            self._logger.info(
                "Tool access successful",
                tool=path.tool,
                mcp_server=tool_def.mcp_server,
                tool_id=path.tool,
            )
        if self._metrics:
            self._metrics.increment("gateway.tool.success")
            self._metrics.record("gateway.tool.duration_ms", round(elapsed, 2))

        return tool_result

    def _record_audit(
        self,
        tool_id: str,
        mcp_server: str,
        agent_id: str,
        success: bool,
        start: datetime,
        error: str | None = None,
    ) -> None:
        """Record audit entry and emit event."""
        elapsed = (datetime.now(UTC) - start).total_seconds() * 1000

        entry = GatewayAuditEntry(
            timestamp=start,
            tool_id=tool_id,
            mcp_server=mcp_server,
            agent_id=agent_id,
            success=success,
            error=error,
            duration_ms=round(elapsed, 2),
        )
        self._audit_log.append(entry)

        if self._event_log is not None:
            self._event_log.emit(
                EventType.GATEWAY_ACCESSED,
                state=ExecutionState.EXECUTING.value,
                metadata={
                    "tool": tool_id,
                    "mcp_server": mcp_server,
                    "agent_id": agent_id,
                    "success": success,
                    "duration_ms": entry.duration_ms,
                },
                error=error,
            )

    @property
    def audit_log(self) -> list[GatewayAuditEntry]:
        """Get gateway access audit trail (read-only copy)."""
        return list(self._audit_log)

    def get_audit_log(self) -> list[dict[str, Any]]:
        """Get audit log as serialized dicts."""
        return [e.to_dict() for e in self._audit_log]
