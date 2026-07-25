"""Tests for the FastAPI REST routes — using TestClient with mock runtime."""

import pytest
from fastapi.testclient import TestClient

from runtime.kitematic_runtime.adapters.checkpoint_adapter import CheckpointPersistenceAdapter
from runtime.kitematic_runtime.adapters.policy_adapter import PolicyEngineAdapter
from runtime.kitematic_runtime.adapters.simple_router import SimpleIntentRouter
from runtime.kitematic_runtime.api.app import create_app
from runtime.kitematic_runtime.api.auth import APIKeyAuthProvider, AuthContext
from runtime.kitematic_runtime.api.events import EventPublisher
from kernel.gateway import MCPToolGateway
from kernel.observability.metrics import MetricsRegistry
from kernel.runtime import (
    KitematicRuntime,
)
from kernel.resources.tool_registry import ToolDefinition, ToolRegistry
from services.checkpoint.repositories.in_memory_checkpoint import InMemoryCheckpointRepository
from services.control_plane.policy.policy_engine import PolicyEngine


class MockMCPClient:
    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        return {"result": "ok"}


@pytest.fixture
def runtime():
    """Real KitematicRuntime with real services, no network."""
    engine = PolicyEngine()
    reg = ToolRegistry()
    reg.register(ToolDefinition(
        tool_id="mcp.database.query",
        mcp_server="db-server",
        description="Query database",
    ))
    gateway = MCPToolGateway(registry=reg)
    gateway.register_client("db-server", MockMCPClient())
    repo = InMemoryCheckpointRepository()

    return KitematicRuntime(
        policy=PolicyEngineAdapter(engine),
        router=SimpleIntentRouter(reg),
        gateway=gateway,
        persistence=CheckpointPersistenceAdapter(repo),
    )


@pytest.fixture
def auth_provider():
    provider = APIKeyAuthProvider()
    provider.add_key("valid-key", AuthContext(tenant_id="t1", agent_id="a1"))
    provider.add_key("tenant-key", AuthContext(tenant_id="t2", agent_id="a2"))
    return provider


@pytest.fixture
def event_publisher():
    return EventPublisher()


@pytest.fixture
def metrics_registry():
    return MetricsRegistry()


@pytest.fixture
def client(runtime, auth_provider, event_publisher, metrics_registry):
    app = create_app(
        runtime=runtime,
        auth_provider=auth_provider,
        event_publisher=event_publisher,
        metrics_registry=metrics_registry,
    )
    with TestClient(app) as c:
        yield c


class TestSubmitIntent:
    """POST /api/v1/intents — submit intent for execution."""

    def test_happy_path_returns_201(self, client):
        resp = client.post(
            "/api/v1/intents",
            json={"agent_id": "agent-1", "action": "mcp.database.query"},
            headers={"X-API-Key": "valid-key"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["success"] is True
        assert data["state"] == "COMPLETED"
        assert data["execution_id"]
        assert data["checkpoint_id"] is not None

    def test_missing_api_key_returns_401(self, client):
        resp = client.post(
            "/api/v1/intents",
            json={"agent_id": "agent-1", "action": "mcp.database.query"},
        )
        assert resp.status_code == 401
        assert "error" in resp.json()

    def test_invalid_api_key_returns_401(self, client):
        resp = client.post(
            "/api/v1/intents",
            json={"agent_id": "agent-1", "action": "mcp.database.query"},
            headers={"X-API-Key": "bad-key"},
        )
        assert resp.status_code == 401

    def test_missing_body_fields_returns_422(self, client):
        resp = client.post(
            "/api/v1/intents",
            json={"agent_id": "agent-1"},
            headers={"X-API-Key": "valid-key"},
        )
        assert resp.status_code == 422

    def test_empty_action_returns_422(self, client):
        resp = client.post(
            "/api/v1/intents",
            json={"agent_id": "agent-1", "action": ""},
            headers={"X-API-Key": "valid-key"},
        )
        assert resp.status_code == 422

    def test_full_payload(self, client):
        resp = client.post(
            "/api/v1/intents",
            json={
                "agent_id": "agent-1",
                "action": "mcp.database.query",
                "parameters": {"query": "SELECT 1"},
            },
            headers={"X-API-Key": "valid-key"},
        )
        assert resp.status_code == 201
        assert resp.json()["success"] is True

    def test_unknown_tool_returns_failure(self, client):
        resp = client.post(
            "/api/v1/intents",
            json={"agent_id": "agent-1", "action": "unknown.tool"},
            headers={"X-API-Key": "valid-key"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["success"] is False
        assert "No tool found" in data["error"]

    def test_metrics_tracked(self, client, metrics_registry):
        client.post(
            "/api/v1/intents",
            json={"agent_id": "agent-1", "action": "mcp.database.query"},
            headers={"X-API-Key": "valid-key"},
        )
        assert metrics_registry.get_counter("api.intents_submitted") >= 1
        assert metrics_registry.get_counter("api.intents_succeeded") >= 1

    def test_event_published(self, client, event_publisher):
        resp = client.post(
            "/api/v1/intents",
            json={"agent_id": "agent-1", "action": "mcp.database.query"},
            headers={"X-API-Key": "valid-key"},
        )
        exec_id = resp.json()["execution_id"]
        assert event_publisher.subscriber_count(exec_id) == 0  # no WS subscribers


class TestGetExecutionStatus:
    """GET /api/v1/executions/{execution_id} — get execution status."""

    def test_existing_execution(self, client):
        post_resp = client.post(
            "/api/v1/intents",
            json={"agent_id": "agent-1", "action": "mcp.database.query"},
            headers={"X-API-Key": "valid-key"},
        )
        exec_id = post_resp.json()["execution_id"]

        get_resp = client.get(
            f"/api/v1/executions/{exec_id}",
            headers={"X-API-Key": "valid-key"},
        )
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["execution_id"] == exec_id
        assert data["state"] == "COMPLETED"

    def test_unknown_execution_returns_403(self, client):
        resp = client.get(
            "/api/v1/executions/nonexistent",
            headers={"X-API-Key": "valid-key"},
        )
        assert resp.status_code == 403

    def test_requires_auth(self, client):
        resp = client.get("/api/v1/executions/any-id")
        assert resp.status_code == 401


class TestHealthCheck:
    """GET /api/v1/health — health check endpoint."""

    def test_returns_ok(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_no_auth_required(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200


class TestMetricsEndpoint:
    """GET /api/v1/metrics — metrics snapshot endpoint."""

    def test_returns_metrics(self, client):
        # Submit an intent to generate metrics
        client.post(
            "/api/v1/intents",
            json={"agent_id": "agent-1", "action": "mcp.database.query"},
            headers={"X-API-Key": "valid-key"},
        )

        resp = client.get(
            "/api/v1/metrics",
            headers={"X-API-Key": "valid-key"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "counters" in data
        assert data["counters"]["api.intents_submitted"] >= 1

    def test_requires_auth(self, client):
        resp = client.get("/api/v1/metrics")
        assert resp.status_code == 401
