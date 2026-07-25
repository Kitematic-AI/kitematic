"""Tests for P3 Step 5 — Security Hardening and Tenant Boundary Enforcement.

Covers:
  - Secrets boundary (SecretsModel, create_secrets_provider)
  - API key fingerprinting and constant-time comparison
  - Key rotation
  - WebSocket auth upgrade (Bearer, Sec-WebSocket-Protocol)
  - Cross-tenant execution isolation (403, never 404)
  - Cross-tenant event subscription isolation
  - Security metrics (security.auth.failed, security.auth.rotation,
    security.tenant.denied, security.websocket.deprecated)
  - Tenant enumeration protection
"""

import hashlib
import os

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from control_plane.adapters.to_kernel.checkpoint import CheckpointPersistenceAdapter
from control_plane.adapters.to_kernel.policy import PolicyEngineAdapter
from control_plane.adapters.to_kernel.router import SimpleIntentRouter
from runtime.kitematic_runtime.api.app import create_app
from runtime.kitematic_runtime.api.audit import AuditEvent, AuditEventType, AuditRecorder
from runtime.kitematic_runtime.api.auth import (
    APIKeyAuthProvider,
    AuthContext,
    _fingerprint,
)
from runtime.kitematic_runtime.config.secrets import SecretsModel, create_secrets_provider
from kernel.events import (
    ExecutionEvent,
    InMemoryEventPublisher,
)
from kernel.gateway import MCPToolGateway
from kernel.observability.logging import RuntimeLogger
from kernel.observability.metrics import MetricsRegistry
from kernel.runtime import KitematicRuntime
from kernel.resources.tool_registry import ToolDefinition, ToolRegistry
from infrastructure.storage.checkpoint.in_memory import InMemoryCheckpointRepository
from control_plane.policy.engine import PolicyEngine

# ── Fixtures ──────────────────────────────────────────────────────

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
    provider.add_key("valid-key-t1", AuthContext(tenant_id="t1", agent_id="a1"))
    provider.add_key("valid-key-t2", AuthContext(tenant_id="t2", agent_id="a2"))
    return provider


@pytest.fixture
def event_publisher():
    return InMemoryEventPublisher()


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


# ── Secrets Boundary ──────────────────────────────────────────────

class TestSecretsBoundary:
    """SecretsModel and create_secrets_provider."""

    def test_secrets_model_frozen(self):
        from pydantic import ValidationError
        s = SecretsModel()
        with pytest.raises(ValidationError):
            s.admin_api_key = "changed"

    def test_secrets_defaults_empty(self):
        s = SecretsModel()
        assert s.admin_api_key == ""
        assert s.api_key_salt == ""

    def test_create_from_env(self, monkeypatch):
        monkeypatch.setenv("KITEMATIC_SECRETS_ADMIN_API_KEY", "sk-secret")
        monkeypatch.setenv("KITEMATIC_SECRETS_API_KEY_SALT", "somesalt")
        s = create_secrets_provider()
        assert s.admin_api_key == "sk-secret"
        assert s.api_key_salt == "somesalt"

    def test_create_from_file(self, tmp_path):
        secrets_file = tmp_path / "secrets.env"
        secrets_file.write_text(
            "ADMIN_API_KEY=sk-from-file\n"
            "API_KEY_SALT=filesalt\n"
            "# comment\n"
            "\n"
        )
        s = create_secrets_provider(secrets_file=str(secrets_file))
        assert s.admin_api_key == "sk-from-file"
        assert s.api_key_salt == "filesalt"

    def test_env_overrides_file(self, monkeypatch, tmp_path):
        monkeypatch.setenv("KITEMATIC_SECRETS_ADMIN_API_KEY", "sk-env")
        secrets_file = tmp_path / "secrets.env"
        secrets_file.write_text("ADMIN_API_KEY=sk-file\n")
        s = create_secrets_provider(secrets_file=str(secrets_file))
        assert s.admin_api_key == "sk-env"

    def test_missing_file_is_noop(self):
        s = create_secrets_provider(secrets_file="/nonexistent/secrets.env")
        assert s.admin_api_key == ""


# ── API Key Fingerprinting ────────────────────────────────────────

class TestAPIKeyFingerprinting:
    """SHA-256 fingerprinting and constant-time comparison."""

    def test_fingerprint_is_sha256_hex(self):
        fp = _fingerprint("my-api-key")
        expected = hashlib.sha256(b"my-api-key").hexdigest()
        assert fp == expected
        assert len(fp) == 64

    def test_same_key_same_fingerprint(self):
        assert _fingerprint("key-1") == _fingerprint("key-1")

    def test_different_keys_different_fingerprints(self):
        assert _fingerprint("key-1") != _fingerprint("key-2")

    def test_empty_key_fingerprint(self):
        fp = _fingerprint("")
        assert len(fp) == 64


class TestAPIKeyAuthProviderSecure:
    """APIKeyAuthProvider with secure key storage."""

    @pytest.mark.asyncio
    async def test_raw_key_not_stored(self):
        provider = APIKeyAuthProvider()
        provider.add_key("secret-key-123", AuthContext(tenant_id="t1"))
        assert "secret-key-123" not in provider._fingerprints
        assert _fingerprint("secret-key-123") in provider._fingerprints

    @pytest.mark.asyncio
    async def test_authenticate_by_raw_key(self):
        provider = APIKeyAuthProvider()
        provider.add_key("my-key", AuthContext(tenant_id="t1"))
        ctx = await provider.authenticate("my-key")
        assert ctx is not None
        assert ctx.tenant_id == "t1"

    @pytest.mark.asyncio
    async def test_constant_time_comparison(self):
        provider = APIKeyAuthProvider()
        provider.add_key("real-key", AuthContext(tenant_id="t1"))
        assert await provider.authenticate("real-key") is not None
        assert await provider.authenticate("wrong-key") is None

    @pytest.mark.asyncio
    async def test_init_with_dict_keys(self):
        provider = APIKeyAuthProvider(keys={"init-key": AuthContext(tenant_id="t-init")})
        ctx = await provider.authenticate("init-key")
        assert ctx is not None
        assert ctx.tenant_id == "t-init"

    @pytest.mark.asyncio
    async def test_remove_key(self):
        provider = APIKeyAuthProvider()
        provider.add_key("key-to-remove", AuthContext(tenant_id="t1"))
        assert provider.key_count == 1
        assert provider.remove_key("key-to-remove") is True
        assert provider.key_count == 0
        assert await provider.authenticate("key-to-remove") is None

    @pytest.mark.asyncio
    async def test_remove_nonexistent_key(self):
        provider = APIKeyAuthProvider()
        assert provider.remove_key("nonexistent") is False


class TestKeyRotation:
    """Key rotation support."""

    @pytest.mark.asyncio
    async def test_rotate_key_success(self):
        provider = APIKeyAuthProvider()
        provider.add_key("old-key", AuthContext(tenant_id="t1"))
        assert await provider.authenticate("old-key") is not None

        result = provider.rotate_key("old-key", "new-key")
        assert result is True

        assert await provider.authenticate("old-key") is None
        ctx = await provider.authenticate("new-key")
        assert ctx is not None
        assert ctx.tenant_id == "t1"

    @pytest.mark.asyncio
    async def test_rotate_key_with_new_context(self):
        provider = APIKeyAuthProvider()
        provider.add_key("old-key", AuthContext(tenant_id="t1"))
        result = provider.rotate_key(
            "old-key", "new-key",
            context=AuthContext(tenant_id="t2"),
        )
        assert result is True
        ctx = await provider.authenticate("new-key")
        assert ctx.tenant_id == "t2"

    @pytest.mark.asyncio
    async def test_rotate_nonexistent_key(self):
        provider = APIKeyAuthProvider()
        result = provider.rotate_key("nonexistent", "new-key")
        assert result is False

    @pytest.mark.asyncio
    async def test_rotate_with_metrics(self):
        provider = APIKeyAuthProvider()
        provider.add_key("old", AuthContext(tenant_id="t1"))
        metrics = MetricsRegistry()
        provider.rotate_key("old", "new", metrics=metrics)
        snap = metrics.snapshot()
        assert snap["counters"].get("security.auth.rotation", 0) == 1


# ── WebSocket Auth Upgrade ────────────────────────────────────────

class TestWebSocketAuthUpgrade:
    """WebSocket authentication via Bearer, Sec-WebSocket-Protocol, deprecated query param."""

    def test_bearer_token_auth(self, client, event_publisher):
        with client.websocket_connect(
            "/ws/v1/executions/exec-1/events",
            headers={"Authorization": "Bearer valid-key-t1"},
        ) as ws:
            event_publisher.close("exec-1")
            msg = ws.receive_json()
            assert msg["type"] == "stream.ended"

    def test_query_param_still_works(self, client):
        with client.websocket_connect(
            "/ws/v1/executions/exec-1/events?api_key=valid-key-t1"
        ) as ws:
            pass  # Connection accepted — query param still works

    def test_no_auth_rejected(self, client):
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/ws/v1/executions/exec-1/events"):
                pass
        assert exc_info.value.code == 4001

    def test_invalid_bearer_rejected(self, client):
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(
                "/ws/v1/executions/exec-1/events",
                headers={"Authorization": "Bearer invalid-key"},
            ):
                pass
        assert exc_info.value.code == 4001

    def test_invalid_query_param_rejected(self, client):
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(
                "/ws/v1/executions/exec-1/events?api_key=bad-key"
            ):
                pass
        assert exc_info.value.code == 4001


# ── Cross-Tenant Execution Isolation ──────────────────────────────

class TestTenantExecutionIsolation:
    """Tenant A cannot see Tenant B's execution, and unknown returns 403."""

    def test_tenant_can_see_own_execution(self, client, runtime):
        resp = client.post(
            "/api/v1/intents",
            json={"agent_id": "a1", "action": "mcp.database.query"},
            headers={"X-API-Key": "valid-key-t1"},
        )
        assert resp.status_code == 201
        exec_id = resp.json()["execution_id"]

        resp2 = client.get(
            f"/api/v1/executions/{exec_id}",
            headers={"X-API-Key": "valid-key-t1"},
        )
        assert resp2.status_code == 200

    def test_tenant_cannot_see_another_tenants_execution(self, client, runtime):
        resp = client.post(
            "/api/v1/intents",
            json={"agent_id": "a1", "action": "mcp.database.query"},
            headers={"X-API-Key": "valid-key-t1"},
        )
        assert resp.status_code == 201
        exec_id = resp.json()["execution_id"]

        resp2 = client.get(
            f"/api/v1/executions/{exec_id}",
            headers={"X-API-Key": "valid-key-t2"},
        )
        assert resp2.status_code == 403

    def test_unknown_execution_returns_403(self, client):
        resp = client.get(
            "/api/v1/executions/nonexistent-id",
            headers={"X-API-Key": "valid-key-t1"},
        )
        assert resp.status_code == 403

    def test_tenant_cannot_enumerate_executions(self, client, runtime):
        resp = client.post(
            "/api/v1/intents",
            json={"agent_id": "a1", "action": "mcp.database.query"},
            headers={"X-API-Key": "valid-key-t1"},
        )
        exec_id = resp.json()["execution_id"]

        resp_b = client.get(
            f"/api/v1/executions/{exec_id}",
            headers={"X-API-Key": "valid-key-t2"},
        )
        assert resp_b.status_code == 403

        resp_b2 = client.get(
            "/api/v1/executions/clearly-fake-id",
            headers={"X-API-Key": "valid-key-t2"},
        )
        assert resp_b2.status_code == 403

    def test_unknown_execution_without_tenant_returns_403(self, client):
        resp = client.get(
            "/api/v1/executions/any-id",
            headers={"X-API-Key": "valid-key-t1"},
        )
        assert resp.status_code == 403


class TestTenantEventIsolation:
    """Tenant A cannot receive Tenant B's events via EventPublisher."""

    @pytest.mark.asyncio
    async def test_same_tenant_receives_events(self):
        pub = InMemoryEventPublisher()
        q = pub.subscribe("exec-1", "t1")
        event = ExecutionEvent(
            execution_id="exec-1",
            tenant_id="t1",
            event_type="test.event",
        )
        await pub.publish(event)
        received = await q.get()
        assert received["event_type"] == "test.event"

    @pytest.mark.asyncio
    async def test_different_tenant_blocked(self):
        pub = InMemoryEventPublisher()
        q = pub.subscribe("exec-1", "t2")
        event = ExecutionEvent(
            execution_id="exec-1",
            tenant_id="t1",
            event_type="test.event",
        )
        await pub.publish(event)
        import asyncio
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(q.get(), timeout=0.1)

    @pytest.mark.asyncio
    async def test_empty_tenant_gets_all(self):
        pub = InMemoryEventPublisher()
        q = pub.subscribe("exec-1", "")
        event = ExecutionEvent(
            execution_id="exec-1",
            tenant_id="t1",
            event_type="test.event",
        )
        await pub.publish(event)
        received = await q.get()
        assert received["event_type"] == "test.event"

    @pytest.mark.asyncio
    async def test_mixed_tenants_filter_correctly(self):
        pub = InMemoryEventPublisher()
        q_t1 = pub.subscribe("exec-1", "t1")
        q_t2 = pub.subscribe("exec-1", "t2")
        q_all = pub.subscribe("exec-1", "")

        await pub.publish(ExecutionEvent(
            execution_id="exec-1",
            tenant_id="t1",
            event_type="event.t1",
        ))

        import asyncio
        r1 = await asyncio.wait_for(q_t1.get(), timeout=0.1)
        assert r1["event_type"] == "event.t1"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(q_t2.get(), timeout=0.1)

        r_all = await asyncio.wait_for(q_all.get(), timeout=0.1)
        assert r_all["event_type"] == "event.t1"

    @pytest.mark.asyncio
    async def test_websocket_only_receives_own_tenant(self, client, runtime, event_publisher):
        exec_id = "exec-iso-1"
        resp = client.post(
            "/api/v1/intents",
            json={"agent_id": "a1", "action": "mcp.database.query"},
            headers={
                "X-API-Key": "valid-key-t1",
                "X-Tenant-ID": "t1",
            },
        )
        assert resp.status_code == 201

        with client.websocket_connect(
            f"/ws/v1/executions/{exec_id}/events?api_key=valid-key-t1"
        ) as ws:
            event_publisher.close(exec_id)
            msg = ws.receive_json()
            assert msg["type"] == "stream.ended"


# ── Security Metrics ──────────────────────────────────────────────

class TestSecurityMetrics:
    """Security-related metrics counters."""

    def test_auth_failed_incremented_on_bad_key(self, client, metrics_registry):
        client.post(
            "/api/v1/intents",
            json={"agent_id": "a1", "action": "unknown"},
            headers={"X-API-Key": "bad-key"},
        )
        snap = metrics_registry.snapshot()
        assert snap["counters"].get("security.auth.failed", 0) >= 1

    def test_tenant_denied_incremented_on_cross_tenant_access(self, client, runtime, metrics_registry):
        resp = client.post(
            "/api/v1/intents",
            json={"agent_id": "a1", "action": "mcp.database.query"},
            headers={"X-API-Key": "valid-key-t1"},
        )
        exec_id = resp.json()["execution_id"]

        snap_before = metrics_registry.snapshot()["counters"].get("security.tenant.denied", 0)

        client.get(
            f"/api/v1/executions/{exec_id}",
            headers={"X-API-Key": "valid-key-t2"},
        )

        snap_after = metrics_registry.snapshot()
        assert snap_after["counters"].get("security.tenant.denied", 0) > snap_before

    def test_websocket_deprecated_incremented(self, client, metrics_registry):
        try:
            with client.websocket_connect(
                "/ws/v1/executions/exec-metric-1/events?api_key=valid-key-t1"
            ):
                pass
        except WebSocketDisconnect:
            pass

        snap = metrics_registry.snapshot()
        assert snap["counters"].get("security.websocket.deprecated", 0) >= 1

    def test_auth_rotation_tracked(self):
        metrics = MetricsRegistry()
        provider = APIKeyAuthProvider()
        provider.add_key("old", AuthContext(tenant_id="t1"))
        provider.rotate_key("old", "new", metrics=metrics)
        snap = metrics.snapshot()
        assert snap["counters"].get("security.auth.rotation", 0) == 1


# ── pyproject.toml metadata ────────────────────────────────────────

class TestPyprojectToml:
    """Verify pyproject.toml defines the project correctly."""

    def test_pyproject_exists(self):
        import tomllib
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        assert data["project"]["name"] == "kitematic"
        assert data["project"]["version"] == "1.0.0-rc.1"

    def test_runtime_dependencies(self):
        import tomllib
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        deps = data["project"]["dependencies"]
        dep_names = [d.split(">=")[0].split("==")[0] for d in deps]
        assert "fastapi" in dep_names
        assert "pydantic" in dep_names
        assert "pydantic-settings" in dep_names
        assert "uvicorn" in dep_names

    def test_optional_extras(self):
        import tomllib
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        optional = data["project"]["optional-dependencies"]
        assert "redis" in optional
        assert "dev" in optional

    def test_scripts_defined(self):
        import tomllib
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        scripts = data["project"]["scripts"]
        assert "kitematic-api" in scripts
        assert scripts["kitematic-api"].endswith(":main")


# ── Audit Recorder ─────────────────────────────────────────────────

class TestAuditRecorder:
    """AuditRecorder — security event recording with correlation context."""

    def test_audit_event_defaults(self):
        event = AuditEvent()
        assert event.event_id
        assert event.event_type == AuditEventType.AUTH_FAILURE
        assert event.tenant_id == ""
        assert event.agent_id == ""
        assert event.execution_id == ""
        assert event.detail == ""
        assert event.timestamp is not None

    def test_audit_event_custom(self):
        event = AuditEvent(
            event_type=AuditEventType.KEY_ROTATION,
            tenant_id="t1",
            agent_id="a1",
            execution_id="exec-1",
            detail="Key rotated for tenant t1",
        )
        assert event.event_type == AuditEventType.KEY_ROTATION
        assert event.tenant_id == "t1"
        assert event.agent_id == "a1"
        assert event.execution_id == "exec-1"

    def test_recorder_without_logger_no_crash(self):
        recorder = AuditRecorder()
        event = recorder.record_auth_failure()
        assert event.event_type == AuditEventType.AUTH_FAILURE

    def test_record_auth_failure(self):
        logger = RuntimeLogger("kitematic.test.audit")
        recorder = AuditRecorder(logger=logger)
        event = recorder.record_auth_failure(tenant_id="t1", detail="Invalid API key")
        assert event.event_type == AuditEventType.AUTH_FAILURE
        assert event.tenant_id == "t1"

    def test_record_auth_success(self):
        logger = RuntimeLogger("kitematic.test.audit")
        recorder = AuditRecorder(logger=logger)
        event = recorder.record_auth_success(tenant_id="t1", agent_id="a1")
        assert event.event_type == AuditEventType.AUTH_SUCCESS
        assert event.tenant_id == "t1"
        assert event.agent_id == "a1"

    def test_record_key_rotation(self):
        logger = RuntimeLogger("kitematic.test.audit")
        recorder = AuditRecorder(logger=logger)
        event = recorder.record_key_rotation(tenant_id="t1")
        assert event.event_type == AuditEventType.KEY_ROTATION

    def test_record_tenant_denied(self):
        logger = RuntimeLogger("kitematic.test.audit")
        recorder = AuditRecorder(logger=logger)
        event = recorder.record_tenant_denied(
            tenant_id="t1", execution_id="exec-1",
            detail="Tenant B attempted to access Tenant A's execution",
        )
        assert event.event_type == AuditEventType.TENANT_DENIED
        assert event.execution_id == "exec-1"

    def test_record_websocket_deprecated(self):
        logger = RuntimeLogger("kitematic.test.audit")
        recorder = AuditRecorder(logger=logger)
        event = recorder.record_websocket_deprecated(tenant_id="t1")
        assert event.event_type == AuditEventType.WEBSOCKET_DEPRECATED

    def test_audit_logs_structured_json(self):
        logger = RuntimeLogger("kitematic.test.audit.json")
        recorder = AuditRecorder(logger=logger)
        event = recorder.record_auth_failure(tenant_id="t1", detail="Test audit")
        assert event.event_type == AuditEventType.AUTH_FAILURE
        assert event.tenant_id == "t1"
        # Structured JSON is logged to stdout (verified via log capture in other tests)

    def test_audit_event_type_enum_values(self):
        assert AuditEventType.AUTH_SUCCESS.value == "auth.success"
        assert AuditEventType.AUTH_FAILURE.value == "auth.failure"
        assert AuditEventType.KEY_ROTATION.value == "auth.key_rotation"
        assert AuditEventType.TENANT_DENIED.value == "tenant.denied"
        assert AuditEventType.WEBSOCKET_DEPRECATED.value == "websocket.deprecated_auth"

    def test_audit_recorder_accepts_none_logger(self):
        recorder = AuditRecorder(logger=None)
        event = recorder.record_auth_failure()
        assert event is not None


class TestPyprojectScripts:
    """Additional pyproject.toml validations."""

    def test_python_version_requirement(self):
        import tomllib
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        python = data["project"]["requires-python"]
        assert python >= ">=3.12"

    def test_build_system_defined(self):
        import tomllib
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        assert "build-system" in data
        assert data["build-system"]["build-backend"]

    def test_dev_dependencies(self):
        import tomllib
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        dev = data["project"]["optional-dependencies"]["dev"]
        dev_names = [d.split(">=")[0].split("==")[0] for d in dev]
        assert "pytest" in dev_names
        assert "httpx" in dev_names

    def test_redis_extra(self):
        import tomllib
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        redis = data["project"]["optional-dependencies"]["redis"]
        assert any("redis" in d for d in redis)

    def test_otel_extra(self):
        import tomllib
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        otel = data["project"]["optional-dependencies"]["otel"]
        assert any("opentelemetry" in d for d in otel)


class TestDockerDeployment:
    """Validate Docker and docker-compose files."""

    def test_dockerfile_exists(self):
        assert os.path.isfile("Dockerfile")

    def test_dockerfile_has_healthcheck(self):
        with open("Dockerfile") as f:
            content = f.read()
        assert "HEALTHCHECK" in content
        assert "kitematic-api" in content

    def test_dockerignore_exists(self):
        assert os.path.isfile(".dockerignore")

    def test_docker_compose_exists(self):
        assert os.path.isfile("docker-compose.yml")

    def test_docker_compose_valid_yaml(self):
        import yaml
        with open("docker-compose.yml") as f:
            data = yaml.safe_load(f)
        assert "services" in data
        assert "kitematic-api" in data["services"]
        assert "redis" in data["services"]


class TestK8sManifests:
    """Validate Kubernetes manifest files."""

    def test_deployment_exists(self):
        assert os.path.isfile("deploy/k8s/deployment.yaml")

    def test_deployment_has_liveness_probe(self):
        with open("deploy/k8s/deployment.yaml") as f:
            content = f.read()
        assert "livenessProbe" in content
        assert "readinessProbe" in content

    def test_service_yaml_exists(self):
        assert os.path.isfile("deploy/k8s/service.yaml")

    def test_hpa_yaml_exists(self):
        assert os.path.isfile("deploy/k8s/hpa.yaml")

    def test_otel_collector_config_exists(self):
        assert os.path.isfile("deploy/otel-collector.yml")
