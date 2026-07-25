"""Tests for MCPToolGateway — concrete ToolGateway implementation.

Verifies:
  - Successful tool access through gateway
  - Tool not registered → GatewayAccessError
  - MCP client not found → GatewayAccessError
  - MCP client failure → GatewayAccessError
  - Audit log recording
  - Event emission
  - Multi-server routing
  - ToolResult typing
"""


import pytest

from kernel.events import EventLog, EventType
from kernel.exceptions import GatewayAccessError
from kernel.gateway import MCPToolGateway
from kernel.runtime import ExecutionPath, Intent, ToolResult
from kernel.resources.tool_registry import ToolDefinition, ToolRegistry

# ── Mock MCP Client ─────────────────────────────────────────────────────


class MockMCPClient:
    """Mock MCP client for testing."""

    def __init__(self, return_value: dict | None = None, raise_error: bool = False):
        self._return_value = return_value or {"output": "ok"}
        self._raise_error = raise_error
        self.call_count = 0
        self.call_args: list[tuple] = []

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        self.call_count += 1
        self.call_args.append((tool_name, arguments))
        if self._raise_error:
            raise RuntimeError("MCP server unavailable")
        return self._return_value


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def registry():
    reg = ToolRegistry()
    reg.register(ToolDefinition(tool_id="mcp.db.query", mcp_server="db-server"))
    reg.register(ToolDefinition(tool_id="mcp.file.read", mcp_server="file-server"))
    return reg


@pytest.fixture
def mock_client():
    return MockMCPClient(return_value={"result": "data"})


@pytest.fixture
def mock_client_file():
    return MockMCPClient(return_value={"content": "file content"})


@pytest.fixture
def gateway(registry, mock_client, mock_client_file):
    return MCPToolGateway(
        registry=registry,
        clients={
            "db-server": mock_client,
            "file-server": mock_client_file,
        },
    )


@pytest.fixture
def intent():
    return Intent(agent_id="a1", action="query")


# ── Access Tests ────────────────────────────────────────────────────────


class TestToolAccess:
    @pytest.mark.asyncio
    async def test_successful_access(self, gateway, intent):
        path = ExecutionPath(tool="mcp.db.query", parameters={"sql": "SELECT 1"})
        result = await gateway.access_tool(path, intent)
        assert result.success is True
        assert result.data == {"result": "data"}
        assert result.error is None

    @pytest.mark.asyncio
    async def test_access_returns_typed_tool_result(self, gateway, intent):
        path = ExecutionPath(tool="mcp.db.query")
        result = await gateway.access_tool(path, intent)
        assert isinstance(result, ToolResult)

    @pytest.mark.asyncio
    async def test_access_passes_parameters_to_client(self, gateway, mock_client, intent):
        path = ExecutionPath(tool="mcp.db.query", parameters={"sql": "SELECT 1"})
        await gateway.access_tool(path, intent)
        assert mock_client.call_args[0] == ("mcp.db.query", {"sql": "SELECT 1"})

    @pytest.mark.asyncio
    async def test_access_unregistered_tool_raises(self, gateway, intent):
        path = ExecutionPath(tool="mcp.nonexistent.tool")
        with pytest.raises(GatewayAccessError):
            await gateway.access_tool(path, intent)

    @pytest.mark.asyncio
    async def test_access_no_client_raises(self, registry, intent):
        gateway = MCPToolGateway(registry=registry)
        path = ExecutionPath(tool="mcp.db.query")
        with pytest.raises(GatewayAccessError):
            await gateway.access_tool(path, intent)

    @pytest.mark.asyncio
    async def test_mcp_client_failure_raises(self, intent):
        registry = ToolRegistry()
        registry.register(ToolDefinition(tool_id="t1", mcp_server="s1"))
        failing_client = MockMCPClient(raise_error=True)
        gateway = MCPToolGateway(registry=registry, clients={"s1": failing_client})
        path = ExecutionPath(tool="t1")
        with pytest.raises(GatewayAccessError):
            await gateway.access_tool(path, intent)

    @pytest.mark.asyncio
    async def test_multi_server_routing(self, gateway, mock_client, mock_client_file, intent):
        db_path = ExecutionPath(tool="mcp.db.query")
        file_path = ExecutionPath(tool="mcp.file.read")
        await gateway.access_tool(db_path, intent)
        await gateway.access_tool(file_path, intent)
        assert mock_client.call_count == 1
        assert mock_client_file.call_count == 1


# ── Audit Log Tests ─────────────────────────────────────────────────────


class TestAuditLog:
    @pytest.mark.asyncio
    async def test_audit_recorded_on_success(self, gateway, intent):
        path = ExecutionPath(tool="mcp.db.query")
        await gateway.access_tool(path, intent)
        assert len(gateway.audit_log) == 1
        entry = gateway.audit_log[0]
        assert entry.tool_id == "mcp.db.query"
        assert entry.mcp_server == "db-server"
        assert entry.agent_id == "a1"
        assert entry.success is True
        assert entry.error is None

    @pytest.mark.asyncio
    async def test_audit_recorded_on_failure(self, gateway, intent):
        path = ExecutionPath(tool="mcp.nonexistent.tool")
        try:
            await gateway.access_tool(path, intent)
        except GatewayAccessError:
            pass
        assert len(gateway.audit_log) == 1
        entry = gateway.audit_log[0]
        assert entry.success is False
        assert entry.error is not None

    @pytest.mark.asyncio
    async def test_audit_log_read_only(self, gateway, intent):
        path = ExecutionPath(tool="mcp.db.query")
        await gateway.access_tool(path, intent)
        log = gateway.audit_log
        log.clear()
        assert len(gateway.audit_log) == 1

    @pytest.mark.asyncio
    async def test_get_audit_log_serialized(self, gateway, intent):
        path = ExecutionPath(tool="mcp.db.query")
        await gateway.access_tool(path, intent)
        serialized = gateway.get_audit_log()
        assert len(serialized) == 1
        assert "timestamp" in serialized[0]
        assert "tool_id" in serialized[0]


# ── Event Emission Tests ────────────────────────────────────────────────


class TestEventEmission:
    @pytest.mark.asyncio
    async def test_event_emitted_on_success(self, gateway, intent):
        event_log = EventLog("exec-1")
        gateway.set_event_log(event_log)
        path = ExecutionPath(tool="mcp.db.query")
        await gateway.access_tool(path, intent)
        events = event_log.get_events_by_type(EventType.GATEWAY_ACCESSED)
        assert len(events) == 1
        assert events[0].metadata["tool"] == "mcp.db.query"
        assert events[0].metadata["success"] is True

    @pytest.mark.asyncio
    async def test_event_emitted_on_failure(self, gateway, intent):
        event_log = EventLog("exec-1")
        gateway.set_event_log(event_log)
        path = ExecutionPath(tool="mcp.nonexistent.tool")
        try:
            await gateway.access_tool(path, intent)
        except GatewayAccessError:
            pass
        events = event_log.get_events_by_type(EventType.GATEWAY_ACCESSED)
        assert len(events) == 1
        assert events[0].metadata["success"] is False
        assert events[0].error is not None

    @pytest.mark.asyncio
    async def test_no_event_log_no_crash(self, gateway, intent):
        path = ExecutionPath(tool="mcp.db.query")
        result = await gateway.access_tool(path, intent)
        assert result.success is True


# ── Client Registration Tests ───────────────────────────────────────────


class TestClientRegistration:
    def test_register_client(self, registry):
        gateway = MCPToolGateway(registry=registry)
        client = MockMCPClient()
        gateway.register_client("new-server", client)
        assert "new-server" in gateway._clients
