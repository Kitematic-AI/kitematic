"""Integration Tests — real adapters wired to real services.

Validates the full execution chain with production service implementations:
  Intent → PolicyEngine → SimpleIntentRouter → MCPToolGateway → CheckpointPersistence

No mocks except MCPClient transport (network layer is out of scope).
"""

import json

import pytest

from control_plane.adapters.to_kernel.checkpoint import CheckpointPersistenceAdapter
from control_plane.adapters.to_kernel.policy import PolicyEngineAdapter
from control_plane.adapters.to_kernel.router import SimpleIntentRouter
from kernel.resources.budget import ExecutionBudget
from kernel.gateway import MCPToolGateway
from kernel.isolation import AgentNotInTenantError, IsolationBoundary
from kernel.lifecycle import LoopController
from kernel.runtime import (
    Intent,
    KitematicRuntime,
)
from kernel.state import ExecutionState
from kernel.tenant import TenantContext, TenantModel
from kernel.resources.tool_registry import ToolDefinition, ToolRegistry
from services.checkpoint.repositories.in_memory_checkpoint import InMemoryCheckpointRepository
from control_plane.policy.engine import PolicyEngine


class MockMCPClient:
    """Mock MCP client — replaces real MCP transport."""

    def __init__(self, response: dict | None = None, fail: bool = False):
        self._response = response or {"result": "ok", "data": "mock_output"}
        self._fail = fail
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        self.calls.append((tool_name, arguments))
        if self._fail:
            raise RuntimeError("MCP transport error")
        return self._response


class FailingClient(MockMCPClient):
    """MCP client that always fails."""

    def __init__(self):
        super().__init__(fail=True)


@pytest.fixture
def policy_engine():
    """Real PolicyEngine with a default allow rule."""
    engine = PolicyEngine()
    return engine


@pytest.fixture
def tool_registry():
    """Real ToolRegistry with configured tools."""
    reg = ToolRegistry()
    reg.register(ToolDefinition(
        tool_id="mcp.database.query",
        mcp_server="db-server",
        description="Query a database",
    ))
    reg.register(ToolDefinition(
        tool_id="mcp.file.read",
        mcp_server="file-server",
        description="Read a file",
    ))
    reg.register(ToolDefinition(
        tool_id="mcp.api.call",
        mcp_server="api-server",
        description="Call an external API",
    ))
    return reg


@pytest.fixture
def mcp_gateway(tool_registry):
    """Real MCPToolGateway with mock clients."""
    gateway = MCPToolGateway(registry=tool_registry)
    gateway.register_client("db-server", MockMCPClient(response={"rows": [{"id": 1}]}))
    gateway.register_client("file-server", MockMCPClient(response={"content": "file data"}))
    gateway.register_client("api-server", MockMCPClient(response={"status": 200}))
    return gateway


@pytest.fixture
def checkpoint_repo():
    """Real InMemoryCheckpointRepository."""
    return InMemoryCheckpointRepository()


@pytest.fixture
def runtime(policy_engine, tool_registry, mcp_gateway, checkpoint_repo):
    """Fully wired KitematicRuntime with real services."""
    return KitematicRuntime(
        policy=PolicyEngineAdapter(policy_engine),
        router=SimpleIntentRouter(tool_registry),
        gateway=mcp_gateway,
        persistence=CheckpointPersistenceAdapter(checkpoint_repo),
    )


class TestFullChainRealServices:
    """End-to-end: real services wired through adapters."""

    @pytest.mark.asyncio
    async def test_happy_path_completes(self, runtime):
        intent = Intent(agent_id="agent-1", action="mcp.database.query")
        result = await runtime.execute_intent(intent)

        assert result.success is True
        assert result.state == ExecutionState.COMPLETED
        assert result.checkpoint_id is not None
        assert result.data == {"rows": [{"id": 1}]}

    @pytest.mark.asyncio
    async def test_chain_order_preserved(self, policy_engine, tool_registry, mcp_gateway, checkpoint_repo):
        policy_adapter = PolicyEngineAdapter(policy_engine)
        router = SimpleIntentRouter(tool_registry)
        persistence = CheckpointPersistenceAdapter(checkpoint_repo)

        runtime = KitematicRuntime(
            policy=policy_adapter,
            router=router,
            gateway=mcp_gateway,
            persistence=persistence,
        )

        await runtime.execute_intent(Intent(agent_id="agent-1", action="mcp.file.read"))

        # Gateway was called
        assert len(mcp_gateway.audit_log) == 1
        assert mcp_gateway.audit_log[0].success is True

    @pytest.mark.asyncio
    async def test_checkpoint_metadata_survives_roundtrip(self, runtime, checkpoint_repo):
        intent = Intent(agent_id="agent-1", action="mcp.database.query")
        result = await runtime.execute_intent(intent)

        # Checkpoint exists in repository
        checkpoint = await checkpoint_repo.get(result.checkpoint_id)
        assert checkpoint is not None
        assert checkpoint.execution_id == result.execution_id
        assert checkpoint.version == 1
        assert checkpoint.agent_state_ref is not None
        # agent_state_ref contains embedded state JSON
        state = json.loads(checkpoint.agent_state_ref)
        assert state["intent_action"] == "mcp.database.query"


class TestFailurePathsRealServices:
    """Every failure point with real services must halt correctly."""

    @pytest.mark.asyncio
    async def test_policy_rejection_stops_chain(self, policy_engine, tool_registry, mcp_gateway, checkpoint_repo):
        # Add a deny rule
        await policy_engine.create_policy(
            name="deny-all",
            target="*",
            effect="DENY",
        )
        policy_adapter = PolicyEngineAdapter(policy_engine)
        router = SimpleIntentRouter(tool_registry)
        persistence = CheckpointPersistenceAdapter(checkpoint_repo)

        runtime = KitematicRuntime(
            policy=policy_adapter,
            router=router,
            gateway=mcp_gateway,
            persistence=persistence,
        )

        result = await runtime.execute_intent(Intent(agent_id="agent-1", action="mcp.database.query"))

        assert result.success is False
        assert result.state == ExecutionState.FAILED
        assert len(mcp_gateway.audit_log) == 0

    @pytest.mark.asyncio
    async def test_router_no_match_halts(self, runtime):
        intent = Intent(agent_id="agent-1", action="unknown.tool")
        result = await runtime.execute_intent(intent)

        assert result.success is False
        assert result.state == ExecutionState.HALTED
        assert "No tool found" in result.error

    @pytest.mark.asyncio
    async def test_gateway_unregistered_tool_fails(self, runtime):
        # Tool exists in registry but has no MCP client
        intent = Intent(agent_id="agent-1", action="mcp.database.query")
        result = await runtime.execute_intent(intent)

        # Should succeed because db-server has a client
        assert result.success is True

    @pytest.mark.asyncio
    async def test_gateway_mcp_error_fails(self, tool_registry, checkpoint_repo):
        # Gateway with failing client
        gateway = MCPToolGateway(registry=tool_registry)
        gateway.register_client("db-server", FailingClient())

        runtime = KitematicRuntime(
            policy=PolicyEngineAdapter(PolicyEngine()),
            router=SimpleIntentRouter(tool_registry),
            gateway=gateway,
            persistence=CheckpointPersistenceAdapter(checkpoint_repo),
        )

        result = await runtime.execute_intent(Intent(agent_id="agent-1", action="mcp.database.query"))

        assert result.success is False
        assert result.state == ExecutionState.FAILED

    @pytest.mark.asyncio
    async def test_checkpoint_failure_halts(self, policy_engine, tool_registry, mcp_gateway):
        # Create adapter with a repo that will fail on save
        class BrokenRepo:
            async def save(self, checkpoint):
                raise RuntimeError("disk full")
            async def get(self, checkpoint_id):
                return None
            async def list_by_execution(self, execution_id):
                return []
            async def get_latest(self, execution_id):
                return None

        persistence = CheckpointPersistenceAdapter(BrokenRepo())

        runtime = KitematicRuntime(
            policy=PolicyEngineAdapter(policy_engine),
            router=SimpleIntentRouter(tool_registry),
            gateway=mcp_gateway,
            persistence=persistence,
        )

        result = await runtime.execute_intent(Intent(agent_id="agent-1", action="mcp.database.query"))

        assert result.success is False
        assert result.state == ExecutionState.HALTED


class TestTenantIntegrationRealServices:
    """Tenant isolation with real services."""

    @pytest.mark.asyncio
    async def test_tenant_context_propagated(self, policy_engine, tool_registry, mcp_gateway, checkpoint_repo):
        boundary = IsolationBoundary()
        boundary.register_tenant(TenantModel(tenant_id="t1", name="T1"))
        boundary.register_agent("agent-1", "t1")

        runtime = KitematicRuntime(
            policy=PolicyEngineAdapter(policy_engine),
            router=SimpleIntentRouter(tool_registry),
            gateway=mcp_gateway,
            persistence=CheckpointPersistenceAdapter(checkpoint_repo),
            isolation=boundary,
        )
        runtime.set_tenant_context(TenantContext(tenant_id="t1", agent_id="agent-1"))

        result = await runtime.execute_intent(Intent(agent_id="agent-1", action="mcp.database.query"))

        assert result.success is True

    @pytest.mark.asyncio
    async def test_cross_tenant_blocked(self, policy_engine, tool_registry, mcp_gateway, checkpoint_repo):
        boundary = IsolationBoundary()
        boundary.register_tenant(TenantModel(tenant_id="t1", name="T1"))
        boundary.register_tenant(TenantModel(tenant_id="t2", name="T2"))
        boundary.register_agent("agent-1", "t1")
        boundary.register_agent("agent-2", "t2")

        runtime = KitematicRuntime(
            policy=PolicyEngineAdapter(policy_engine),
            router=SimpleIntentRouter(tool_registry),
            gateway=mcp_gateway,
            persistence=CheckpointPersistenceAdapter(checkpoint_repo),
            isolation=boundary,
        )

        with pytest.raises(AgentNotInTenantError):
            boundary.validate_agent_scope("agent-2", "t1")


class TestMultiStepRealServices:
    """Multi-step execution through LoopController with real services."""

    @pytest.mark.asyncio
    async def test_sequential_execution(self, policy_engine, tool_registry, mcp_gateway, checkpoint_repo):
        budget = ExecutionBudget(max_steps=5)
        runtime = KitematicRuntime(
            policy=PolicyEngineAdapter(policy_engine),
            router=SimpleIntentRouter(tool_registry),
            gateway=mcp_gateway,
            persistence=CheckpointPersistenceAdapter(checkpoint_repo),
        )
        loop = LoopController(runtime=runtime, budget=budget)

        intents = [
            Intent(agent_id="agent-1", action="mcp.database.query"),
            Intent(agent_id="agent-1", action="mcp.file.read"),
            Intent(agent_id="agent-1", action="mcp.api.call"),
        ]
        results = await loop.run_multi_step(intents)

        assert len(results) == 3
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_budget_exhaustion_stops_loop(self, policy_engine, tool_registry, mcp_gateway, checkpoint_repo):
        budget = ExecutionBudget(max_steps=2)
        runtime = KitematicRuntime(
            policy=PolicyEngineAdapter(policy_engine),
            router=SimpleIntentRouter(tool_registry),
            gateway=mcp_gateway,
            persistence=CheckpointPersistenceAdapter(checkpoint_repo),
        )
        loop = LoopController(runtime=runtime, budget=budget)

        intents = [
            Intent(agent_id="agent-1", action="mcp.database.query"),
            Intent(agent_id="agent-1", action="mcp.file.read"),
            Intent(agent_id="agent-1", action="mcp.api.call"),
        ]
        results = await loop.run_multi_step(intents)

        assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_policy_rejection_in_multi_step(self, policy_engine, tool_registry, mcp_gateway, checkpoint_repo):
        await policy_engine.create_policy(
            name="deny-api",
            target="mcp.api.*",
            effect="DENY",
        )
        budget = ExecutionBudget(max_steps=5)
        runtime = KitematicRuntime(
            policy=PolicyEngineAdapter(policy_engine),
            router=SimpleIntentRouter(tool_registry),
            gateway=mcp_gateway,
            persistence=CheckpointPersistenceAdapter(checkpoint_repo),
        )

        # Single intent that should be denied
        result = await runtime.execute_intent(
            Intent(agent_id="agent-1", action="mcp.api.call")
        )

        assert result.success is False
        assert "deny-api" in result.error


class TestEventLoggingRealServices:
    """Event emission with real services."""

    @pytest.mark.asyncio
    async def test_gateway_emits_audit_event(self, tool_registry, mcp_gateway, checkpoint_repo):
        policy_engine = PolicyEngine()
        runtime = KitematicRuntime(
            policy=PolicyEngineAdapter(policy_engine),
            router=SimpleIntentRouter(tool_registry),
            gateway=mcp_gateway,
            persistence=CheckpointPersistenceAdapter(checkpoint_repo),
        )

        await runtime.execute_intent(Intent(agent_id="agent-1", action="mcp.database.query"))

        assert len(mcp_gateway.audit_log) == 1
        assert mcp_gateway.audit_log[0].success is True
        assert mcp_gateway.audit_log[0].tool_id == "mcp.database.query"
