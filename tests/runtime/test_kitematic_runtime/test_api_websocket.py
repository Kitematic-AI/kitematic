"""Tests for WebSocket execution event streaming."""

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from runtime.kitematic_runtime.adapters.checkpoint_adapter import CheckpointPersistenceAdapter
from runtime.kitematic_runtime.adapters.policy_adapter import PolicyEngineAdapter
from runtime.kitematic_runtime.adapters.simple_router import SimpleIntentRouter
from runtime.kitematic_runtime.api.app import create_app
from runtime.kitematic_runtime.api.auth import APIKeyAuthProvider, AuthContext
from runtime.kitematic_runtime.api.events import EventPublisher
from runtime.kitematic_runtime.gateway import MCPToolGateway
from runtime.kitematic_runtime.observability.metrics import MetricsRegistry
from runtime.kitematic_runtime.runtime import KitematicRuntime
from runtime.kitematic_runtime.tool_registry import ToolDefinition, ToolRegistry
from services.checkpoint.repositories.in_memory_checkpoint import InMemoryCheckpointRepository
from services.control_plane.policy.policy_engine import PolicyEngine


class MockMCPClient:
    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        return {"result": "ok"}


@pytest.fixture
def runtime():
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


class TestWebSocketAuth:
    """WebSocket connection authentication."""

    def test_connect_without_key_rejected(self, client):
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/ws/v1/executions/exec-1/events"):
                pass
        assert exc_info.value.code == 4001

    def test_connect_with_invalid_key_rejected(self, client):
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(
                "/ws/v1/executions/exec-1/events?api_key=bad-key"
            ):
                pass
        assert exc_info.value.code == 4001


class TestWebSocketEventStream:
    """WebSocket event streaming."""

    @pytest.mark.asyncio
    async def test_connect_and_receive(self, client, event_publisher):
        exec_id = "exec-stream-1"

        with client.websocket_connect(
            f"/ws/v1/executions/{exec_id}/events?api_key=valid-key"
        ) as ws:
            await event_publisher.publish(exec_id, {"type": "event", "seq": 1})
            event_publisher.close(exec_id)

            assert ws.receive_json() == {"type": "event", "seq": 1}
            assert ws.receive_json()["type"] == "stream.ended"

    @pytest.mark.asyncio
    async def test_events_in_order(self, client, event_publisher):
        exec_id = "exec-order-1"

        with client.websocket_connect(
            f"/ws/v1/executions/{exec_id}/events?api_key=valid-key"
        ) as ws:
            await event_publisher.publish(exec_id, {"type": "event.1"})
            await event_publisher.publish(exec_id, {"type": "event.2"})
            await event_publisher.publish(exec_id, {"type": "event.3"})
            event_publisher.close(exec_id)

            assert ws.receive_json()["type"] == "event.1"
            assert ws.receive_json()["type"] == "event.2"
            assert ws.receive_json()["type"] == "event.3"
            assert ws.receive_json()["type"] == "stream.ended"

    @pytest.mark.asyncio
    async def test_multiple_clients(self, client, event_publisher):
        exec_id = "exec-multi-1"

        with client.websocket_connect(
            f"/ws/v1/executions/{exec_id}/events?api_key=valid-key"
        ) as ws1:
            with client.websocket_connect(
                f"/ws/v1/executions/{exec_id}/events?api_key=valid-key"
            ) as ws2:
                await event_publisher.publish(exec_id, {"msg": "broadcast"})
                event_publisher.close(exec_id)

                assert ws1.receive_json()["msg"] == "broadcast"
                assert ws2.receive_json()["msg"] == "broadcast"
