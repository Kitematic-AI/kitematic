"""Tests for SimpleIntentRouter — ABI IntentRouter → ToolRegistry."""

import pytest

from control_plane.adapters.to_kernel.router import SimpleIntentRouter
from kernel.exceptions import OrchestrationError
from kernel.runtime import ExecutionPath, Intent
from kernel.resources.tool_registry import ToolDefinition, ToolRegistry


@pytest.fixture
def registry():
    reg = ToolRegistry()
    reg.register(ToolDefinition(
        tool_id="mcp.database.query",
        mcp_server="db-server",
        description="Query database",
    ))
    reg.register(ToolDefinition(
        tool_id="mcp.file.read",
        mcp_server="file-server",
        description="Read files",
    ))
    reg.register(ToolDefinition(
        tool_id="mcp.api.*",
        mcp_server="api-server",
        description="API tools",
    ))
    return reg


class TestSimpleIntentRouterExactMatch:
    """Tests for exact tool_id matching."""

    @pytest.mark.asyncio
    async def test_exact_match(self, registry):
        router = SimpleIntentRouter(registry)
        intent = Intent(agent_id="agent-1", action="mcp.database.query")

        path = await router.route_intent(intent)

        assert path.tool == "mcp.database.query"
        assert path.adapter == "db-server"
        assert path.parameters == {}

    @pytest.mark.asyncio
    async def test_exact_match_preserves_parameters(self, registry):
        router = SimpleIntentRouter(registry)
        intent = Intent(
            agent_id="agent-1",
            action="mcp.file.read",
            parameters={"path": "/tmp/test.txt"},
        )

        path = await router.route_intent(intent)

        assert path.tool == "mcp.file.read"
        assert path.adapter == "file-server"
        assert path.parameters == {"path": "/tmp/test.txt"}


class TestSimpleIntentRouterPatternMatch:
    """Tests for pattern-based matching."""

    @pytest.mark.asyncio
    async def test_pattern_match(self, registry):
        router = SimpleIntentRouter(registry)
        intent = Intent(agent_id="agent-1", action="mcp.api.*")

        path = await router.route_intent(intent)

        assert path.tool == "mcp.api.*"
        assert path.adapter == "api-server"


class TestSimpleIntentRouterErrors:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_no_match_raises(self, registry):
        router = SimpleIntentRouter(registry)
        intent = Intent(agent_id="agent-1", action="unknown.tool")

        with pytest.raises(OrchestrationError, match="No tool found"):
            await router.route_intent(intent)

    @pytest.mark.asyncio
    async def test_empty_registry_raises(self):
        empty_registry = ToolRegistry()
        router = SimpleIntentRouter(empty_registry)
        intent = Intent(agent_id="agent-1", action="any.action")

        with pytest.raises(OrchestrationError, match="No tool found"):
            await router.route_intent(intent)


class TestSimpleIntentRouterExecutionPath:
    """Tests for ExecutionPath construction."""

    @pytest.mark.asyncio
    async def test_returns_frozen_execution_path(self, registry):
        router = SimpleIntentRouter(registry)
        intent = Intent(agent_id="agent-1", action="mcp.database.query")

        path = await router.route_intent(intent)

        assert isinstance(path, ExecutionPath)
        # ExecutionPath is frozen
        with pytest.raises(AttributeError):
            path.tool = "modified"

    @pytest.mark.asyncio
    async def test_empty_parameters_default(self, registry):
        router = SimpleIntentRouter(registry)
        intent = Intent(agent_id="agent-1", action="mcp.database.query")

        path = await router.route_intent(intent)

        assert path.parameters == {}
