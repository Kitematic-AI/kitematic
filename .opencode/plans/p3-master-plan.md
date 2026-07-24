# P3: Production Hardening & Scale Readiness — Plan

**Phase:** P3 — Production Hardening & Scale Readiness
**Prerequisite:** P2 officially closed ✅
**Status:** READY FOR HUMAN OWNER APPROVAL

---

## Overview

P2 left the system with a solid Runtime core, working adapters, API layer, and 389 passing tests.
Three observability modules were defined and tested but never wired. No graceful shutdown, no
configuration management, no distributed event support. P3 addresses all of these gaps.

**Execution order rationale:**
Observability first (becomes the measurement tool for everything that follows), then lifecycle
(hardening before scaling), then configuration (required for deployment), then distributed
events (scaling), then security (final hardening).

```
P3.1 Observability Wiring  →  P3.2 Lifecycle Hardening  →  P3.3 Configuration  →  P3.4 Distributed Events  →  P3.5 Security Hardening
```

---

## P3 Step 1: Runtime Observability Integration

**Goal:** Transform observability from "defined" to "active". Every execution produces structured
logs, metrics, and traces.

### Scope

| Module | Change |
|--------|--------|
| `runtime.py` | Inject tracer + logger + metrics. Wire at each state transition. |
| `loop.py` | Inject logger + metrics. Log loop lifecycle, budget consumption. |
| `gateway.py` | Inject logger + metrics. Capture MCP call latency. |
| `observability/logging.py` | No changes (already complete). |
| `observability/metrics.py` | No changes (already complete). |
| `observability/tracing.py` | No changes (already complete). |

### Wiring: runtime.py — execute_intent()

| Transition | Line | Action |
|------------|------|--------|
| T1: CREATED → VALIDATING | ~253 | `tracer.start_phase(TracePhase.INTENT_RECEIVED)` + `metrics.increment("runtime.executions.started")` + `logger.info("Execution started")` |
| T2: VALIDATING → AUTHORIZED | ~277 | `tracer.end_phase(success=True)` + `metrics.record("runtime.policy.duration_ms", elapsed)` + `metrics.increment("runtime.policy.allowed")` |
| T2b: Policy rejected | ~268 | `tracer.end_phase(success=False, error=reason)` + `metrics.increment("runtime.policy.rejected")` |
| T3: AUTHORIZED → EXECUTING | ~303 | `tracer.end_phase(success=True)` + `metrics.increment("runtime.capability.allowed")` |
| T4: EXECUTING → CHECKPOINTING | ~339 | `tracer.end_phase(success=True)` + `metrics.record("runtime.gateway.duration_ms", elapsed)` |
| T5: CHECKPOINTING → COMPLETED | ~364 | `tracer.end_phase(success=True)` + `metrics.increment("runtime.executions.succeeded")` + `logger.info("Execution completed")` |
| Any → FAILED/HALTED | various | `tracer.end_phase(success=False, error=...)` + `metrics.increment("runtime.executions.failed")` + `logger.error("Execution failed")` |

### Wiring: loop.py — run_intent()

| Point | Line | Action |
|-------|------|--------|
| Loop start | ~161 | `logger.info("Loop started", execution_id=..., agent_id=...)` |
| After execute_intent() | ~181 | `logger.info("Step completed")` + `metrics.record("runtime.loop.step_duration_ms", elapsed)` |
| Budget exhaustion | ~229 | `logger.warn("Budget exhausted")` + `metrics.increment("runtime.loop.budget_exhausted")` |
| Multi-step iteration | ~298 | `metrics.record("runtime.loop.step_duration_ms", elapsed)` per step |

### Wiring: gateway.py — access_tool()

| Point | Line | Action |
|-------|------|--------|
| Success | ~169 | `logger.info("Tool accessed", tool=..., mcp_server=...)` + `metrics.increment("gateway.access.success")` |
| Registry miss | ~131 | `logger.warn("Tool not registered")` + `metrics.increment("gateway.access.registry_miss")` |
| Client miss | ~145 | `logger.warn("MCP client not found")` + `metrics.increment("gateway.access.client_miss")` |
| MCP failure | ~160 | `logger.error("MCP call failed")` + `metrics.increment("gateway.access.mcp_failure")` |
| Total duration | ~189 | `metrics.record("gateway.access.duration_ms", elapsed)` — already computed |

### Constructor Changes

**runtime.py** — `KitematicRuntime.__init__()` gains optional observability params:
```python
def __init__(self, policy, router, gateway, persistence, isolation=None,
             logger=None, metrics=None, tracer_factory=None):
```

**loop.py** — `LoopController.__init__()` gains optional observability params:
```python
def __init__(self, runtime, budget, tenant_context=None,
             logger=None, metrics=None):
```

**gateway.py** — `MCPToolGateway.__init__()` gains optional observability params:
```python
def __init__(self, registry, clients=None, metrics=None, logger=None):
```

### New Test File

`tests/runtime/test_kitematic_runtime/test_observability_wiring.py` (~20 tests):
- Verify trace phases are produced for successful execution
- Verify trace phases are produced for failed execution
- Verify metrics counters increment on each transition
- Verify metrics histograms record latency
- Verify logger produces structured log entries (via caplog)
- Verify gateway metrics are captured on success, registry miss, client miss, MCP failure
- Verify loop metrics are captured per step
- Verify correlation IDs propagate from logger to trace

### Expected Test Count

```
Existing: 389
New (observability wiring): ~20
P3.1 Total: ~409
```

---

## P3 Step 2: Lifecycle Hardening

**Goal:** Graceful startup, shutdown, and resource cleanup.

### Scope

| Module | Change |
|--------|--------|
| `runtime.py` | Add `KitematicRuntime.stop()` method |
| `loop.py` | Add `LoopController.shutdown()` method |
| `api/app.py` | Add FastAPI lifespan context manager |
| `api/events.py` | Add `EventPublisher.close_all()` method |

### KitematicRuntime.stop()

```python
async def stop(self) -> None:
    """Gracefully stop the runtime.
    
    Actions:
    1. Reject any new execution requests
    2. Wait for in-flight executions to complete (with timeout)
    3. Close gateway connections
    4. Flush observability data
    """
```

State management: Add `_stopping: bool = False` flag.
`execute_intent()` checks this flag at entry — returns `ExecutionResult(success=False, error="Runtime is shutting down")` if True.

### LoopController.shutdown()

```python
async def shutdown(self, timeout_seconds: float = 30.0) -> None:
    """Shutdown the loop controller, draining in-flight work."""
```

### FastAPI Lifespan

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.startup_time = datetime.now(timezone.utc)
    logger = RuntimeLogger("kitematic.runtime.api")
    logger.info("API starting", version=app.version)
    yield
    # Shutdown
    logger.info("API shutting down")
    await runtime.stop()
    event_publisher.close_all()
```

### EventPublisher.close_all()

New method: sends `None` sentinel to all subscriber queues across all executions, then clears the `_subscribers` dict.

### Resource Cleanup Inventory

| Resource | Cleanup |
|----------|---------|
| `app.state.executions` (dict) | Evict entries older than TTL (default 1 hour) |
| `EventPublisher._subscribers` | `close_all()` on shutdown |
| `MCPToolGateway._audit_log` | Already bounded by execution count |
| `LoopController._history` | Evict entries older than TTL |

### New Tests

`tests/runtime/test_kitematic_runtime/test_lifecycle.py` (~10 tests):
- `stop()` prevents new executions
- `stop()` allows in-flight to complete before returning
- FastAPI lifespan calls `stop()` on shutdown
- `EventPublisher.close_all()` clears all subscribers
- Execution history eviction by TTL

### Expected Test Count

```
After P3.1: ~409
New (lifecycle): ~10
P3.2 Total: ~419
```

---

## P3 Step 3: Configuration Layer

**Goal:** Externalize all hardcoded defaults into a `Settings` model loaded from env vars.

### Scope

| Module | Change |
|--------|--------|
| New: `runtime/kitematic_runtime/config.py` | `Settings` model (pydantic-settings) |
| `budget.py` | Read defaults from Settings |
| `tenant.py` | Read ResourceLimits from Settings |
| `observability/logging.py` | Read log level from Settings |
| `api/app.py` | Pass Settings to all constructors |

### Settings Model

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KITEMATIC_")

    # Budget
    budget_max_steps: int = 10
    budget_max_tokens: int = 100_000
    budget_timeout_seconds: int = 3600

    # Tenant defaults
    tenant_max_agents: int = 10
    tenant_max_steps_per_agent: int = 10
    tenant_max_tokens_per_agent: int = 100_000
    tenant_max_concurrent_executions: int = 5
    tenant_max_checkpoints: int = 100

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # API
    api_title: str = "Kitematic Runtime API"
    api_version: str = "0.2.0"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Metrics
    metrics_enabled: bool = True

    # Events
    event_backend: str = "memory"  # memory | redis
    event_redis_url: str | None = None
```

Env vars: `KITEMATIC_BUDGET_MAX_STEPS=20`, `KITEMATIC_LOG_LEVEL=DEBUG`, etc.

### Integration

```python
# create_app() uses Settings
def create_app(settings: Settings | None = None, ...):
    if settings is None:
        settings = Settings()
    ...
```

### New Tests

`tests/runtime/test_kitematic_runtime/test_config.py` (~10 tests):
- Settings defaults are correct
- Settings load from env vars
- Settings override individual fields
- Settings can be passed to create_app()
- Budget reads from settings
- RuntimeLogger reads log level from settings

### Expected Test Count

```
After P3.2: ~419
New (config): ~10
P3.3 Total: ~429
```

---

## P3 Step 4: Distributed Runtime Readiness

**Goal:** Make EventPublisher swappable for Redis/NATS without changing consumers.

### Scope

| Module | Change |
|--------|--------|
| `api/events.py` | Extract ABC `EventPublisherBase`, keep `InMemoryEventPublisher` |
| New: `api/events_redis.py` | `RedisEventPublisher` implementation |

### EventPublisherBase ABC

```python
class EventPublisherBase(ABC):
    @abstractmethod
    def subscribe(self, execution_id: str) -> asyncio.Queue: ...

    @abstractmethod
    def unsubscribe(self, execution_id: str, queue: asyncio.Queue) -> None: ...

    @abstractmethod
    def publish(self, execution_id: str, event: dict[str, Any]) -> None: ...

    @abstractmethod
    def close(self, execution_id: str) -> None: ...

    @abstractmethod
    def close_all(self) -> None: ...

    @property
    @abstractmethod
    def active_executions(self) -> list[str]: ...

    @abstractmethod
    def subscriber_count(self, execution_id: str) -> int: ...
```

### InMemoryEventPublisher (renamed)

Current `EventPublisher` becomes `InMemoryEventPublisher` (concrete, same implementation).
`EventPublisher` becomes an alias for backward compatibility.

### RedisEventPublisher (sketch)

```python
class RedisEventPublisher(EventPublisherBase):
    def __init__(self, redis_url: str):
        self._redis = redis.asyncio.from_url(redis_url)
        self._local_queues: dict[str, list[asyncio.Queue]] = {}

    async def publish(self, execution_id: str, event: dict[str, Any]) -> None:
        await self._redis.xadd(f"events:{execution_id}", event)
        # Also deliver to local subscribers
        for q in self._local_queues.get(execution_id, []):
            q.put_nowait(event)
```

### Factory Function

```python
def create_event_publisher(settings: Settings) -> EventPublisherBase:
    if settings.event_backend == "redis":
        return RedisEventPublisher(settings.event_redis_url)
    return InMemoryEventPublisher()
```

### New Tests

`tests/runtime/test_kitematic_runtime/test_events_distributed.py` (~8 tests):
- `InMemoryEventPublisher` implements all ABC methods (verify ABC)
- ABC cannot be instantiated directly
- Factory creates correct backend type
- RedisEventPublisher cannot be tested without Redis (documented)

### Expected Test Count

```
After P3.3: ~429
New (distributed events): ~8
P3.4 Total: ~437
```

---

## P3 Step 5: Security Hardening

**Goal:** Upgrade WebSocket auth, add API key rotation, improve audit.

### Scope

| Module | Change |
|--------|--------|
| `api/app.py` | WebSocket auth: support `Sec-WebSocket-Protocol` header |
| `api/auth.py` | Add `AuthProvider.validate_key_rotation()` |
| `api/app.py` | Add API key rotation endpoint |
| `api/app.py` | Add audit log endpoint |

### WebSocket Auth Upgrade

Current: `?api_key=<key>` query param (temporary).
New: Primary support for `Sec-WebSocket-Protocol: kitematic-api-key,<key>` header.
Fallback: query param (for browser compat).

```python
# In execution_events():
protocol = websocket.headers.get("sec-websocket-protocol", "")
if "kitematic-api-key," in protocol:
    api_key = protocol.split("kitematic-api-key,")[1].strip()
else:
    api_key = Query(default="")  # fallback
```

### API Key Rotation

```python
# New endpoint: POST /api/v1/auth/rotate
# Accepts: { "old_key": "...", "new_key": "..." }
# Returns: { "rotated": true }
```

Requires APIKeyAuthProvider to support key rotation:
```python
class APIKeyAuthProvider(AuthProvider):
    def rotate_key(self, old_key: str, new_key: str) -> bool:
        """Rotate an API key. Returns True if successful."""
```

### Audit Log Endpoint

```python
# New endpoint: GET /api/v1/audit/gateway
# Returns: list of GatewayAuditEntry dicts
```

### New Tests

`tests/runtime/test_kitematic_runtime/test_security.py` (~8 tests):
- WebSocket auth via Sec-WebSocket-Protocol header
- WebSocket auth fallback to query param
- API key rotation succeeds
- API key rotation with old key fails
- Audit log endpoint returns entries
- Audit log endpoint requires auth

### Expected Test Count

```
After P3.4: ~437
New (security): ~8
P3.5 Total: ~445
```

---

## P3 Final Test Count

```
P2 closure:             389 tests
P3.1 Observability:    +20 tests = 409
P3.2 Lifecycle:        +10 tests = 419
P3.3 Configuration:    +10 tests = 429
P3.4 Distributed:       +8 tests = 437
P3.5 Security:          +8 tests = 445
------------------------------------------
P3 Final:              445 tests (estimated)
```

---

## P3 Execution Order

| Step | Depends On | Key Deliverables |
|------|-----------|------------------|
| **P3.1** Observability Wiring | P2 closure | Wire tracer + logger + metrics into runtime, loop, gateway |
| **P3.2** Lifecycle Hardening | P3.1 | stop(), lifespan, close_all(), cleanup |
| **P3.3** Configuration | P3.2 | Settings model, env vars, externalize defaults |
| **P3.4** Distributed Events | P3.3 | EventPublisherBase ABC, RedisEventPublisher |
| **P3.5** Security | P3.4 | WebSocket auth upgrade, key rotation, audit endpoint |

Each step is independently testable and backward-compatible with P2 tests.
