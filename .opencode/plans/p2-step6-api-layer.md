# P2 Step 6: API Layer — Detailed Implementation Plan

## Objective

Expose KitematicRuntime through an HTTP/WebSocket API layer using FastAPI.
The API layer is a thin transport boundary — it validates requests, authenticates clients,
serializes responses, and streams events. It NEVER makes policy/authorization decisions.

## Architecture

```
HTTP/WS Client
     |
     v
 FastAPI Application
     |
     +-- AuthMiddleware (API Key → AuthContext)
     |       |
     |       v
     +-- Pydantic Contracts (request/response validation)
     |       |
     |       v
     +-- REST Routes (/api/v1/*)
     |       |
     |       v
     +-- WebSocket Handler (/ws/v1/*)
     |       |
     |       v
     +-- EventPublisher (in-memory event broker)
     |
     v
 KitematicRuntime ABI
     |
     v
 Adapters + Services
```

## Responsibility Boundaries

| Layer | Responsibilities |
|-------|-----------------|
| **API Layer** | HTTP transport, auth extraction, request validation, response serialization, WebSocket connections |
| **Runtime** | Intent execution, lifecycle state machine, policy evaluation, gateway access, checkpoint |
| **Policy Engine** | Authorization decisions (ALLOW/DENY) |
| **IsolationBoundary** | Tenant/agent scope enforcement |

**API Layer NEVER:**
- Makes policy decisions ❌
- Accesses tools directly ❌
- Manages tenant authorization logic ❌
- Modifies execution state ❌

## Dependencies

**New (add to project):**
- `fastapi` — Web framework
- `uvicorn` — ASGI server
- `pydantic` — Request/response validation (comes with FastAPI)

**Existing (no changes):**
- `runtime.kitematic_runtime` — Core ABI
- `runtime.kitematic_runtime.observability` — Metrics, tracing, logging

## File Structure

```
runtime/kitematic_runtime/api/
├── __init__.py           # Package exports
├── schemas.py            # Pydantic models (contracts)
├── auth.py               # AuthProvider abstraction + APIKeyAuthProvider
├── events.py             # EventPublisher for WebSocket streaming
└── app.py                # FastAPI application factory + route definitions
```

**Test files:**
```
tests/runtime/test_kitematic_runtime/
├── test_api_schemas.py       # Pydantic contract tests
├── test_api_auth.py          # Auth middleware tests
├── test_api_events.py        # EventPublisher tests
├── test_api_routes.py        # REST endpoint tests (TestClient)
└── test_api_websocket.py     # WebSocket integration tests
```

## Detailed Module Design

### 1. `schemas.py` — Pydantic Contracts

Request/response models that mirror the runtime DTOs but add HTTP validation.

```python
# Request Models
class IntentRequest(BaseModel):
    agent_id: str                          # Required
    action: str                            # Required
    parameters: dict[str, Any] = {}        # Optional

class TenantHeader(BaseModel):
    """Extracted from X-Tenant-ID / X-Agent-ID headers."""
    tenant_id: str
    agent_id: str

# Response Models
class ExecutionResponse(BaseModel):
    execution_id: str
    success: bool
    state: str                             # ExecutionState.value
    checkpoint_id: str | None = None
    data: dict[str, Any] = {}
    error: str | None = None

class ExecutionStatusResponse(BaseModel):
    execution_id: str
    state: str
    agent_id: str
    action: str
    created_at: str
    checkpoint_id: str | None = None

class ErrorResponse(BaseModel):
    error: str
    code: str                              # Exception.code
    details: dict[str, Any] = {}

class HealthResponse(BaseModel):
    status: str
    version: str
    runtime: str

class MetricsResponse(BaseModel):
    counters: dict[str, int]
    histograms: dict[str, dict[str, float]]
    gauges: dict[str, Any]
```

### 2. `auth.py` — Authentication Middleware

```python
class AuthContext(BaseModel):
    """Resolved authentication context."""
    tenant_id: str
    agent_id: str = ""
    permissions: list[str] = []

class AuthProvider(ABC):
    """Protocol for authentication providers."""
    @abstractmethod
    async def authenticate(self, api_key: str) -> AuthContext | None:
        """Validate API key and return auth context. None = rejected."""
        ...

class APIKeyAuthProvider(AuthProvider):
    """Concrete provider: API key → AuthContext via configured key store."""
    def __init__(self, keys: dict[str, AuthContext]):
        self._keys = keys  # api_key → AuthContext mapping

    async def authenticate(self, api_key: str) -> AuthContext | None:
        return self._keys.get(api_key)

# FastAPI dependency
async def get_auth_context(
    request: Request,
    provider: AuthProvider = Depends(...),
) -> AuthContext:
    api_key = request.headers.get("X-API-Key", "")
    ctx = await provider.authenticate(api_key)
    if ctx is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return ctx
```

### 3. `events.py` — EventPublisher for WebSocket

In-memory event broker that bridges runtime EventLog to WebSocket clients.

```python
class EventPublisher:
    """In-memory event broker for streaming execution events to WebSocket clients."""

    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = {}  # exec_id → queues

    def subscribe(self, execution_id: str) -> asyncio.Queue:
        """Subscribe to events for a specific execution."""
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(execution_id, []).append(queue)
        return queue

    def unsubscribe(self, execution_id: str, queue: asyncio.Queue) -> None:
        """Remove a subscriber."""
        subs = self._subscribers.get(execution_id, [])
        if queue in subs:
            subs.remove(queue)

    def publish(self, execution_id: str, event: dict[str, Any]) -> None:
        """Publish an event to all subscribers of an execution."""
        for queue in self._subscribers.get(execution_id, []):
            queue.put_nowait(event)

    def close(self, execution_id: str) -> None:
        """Close all subscribers for an execution (sends sentinel)."""
        for queue in self._subscribers.get(execution_id, []):
            queue.put_nowait(None)  # Sentinel: stream ended
        self._subscribers.pop(execution_id, None)
```

### 4. `app.py` — FastAPI Application Factory + Routes

```python
def create_app(
    runtime: KitematicRuntime,
    loop_controller: LoopController | None = None,
    auth_provider: AuthProvider | None = None,
    event_publisher: EventPublisher | None = None,
) -> FastAPI:
    """Create FastAPI application with runtime wiring."""

app = FastAPI(title="Kitematic Runtime API", version="0.2.0")

# ── REST Endpoints ──────────────────────────────────────────

POST /api/v1/intents
  Body: IntentRequest
  Headers: X-API-Key, X-Tenant-ID, X-Agent-ID
  → ExecutionResponse (201)
  → ErrorResponse (401/422/500)

GET /api/v1/executions/{execution_id}
  Headers: X-API-Key
  → ExecutionStatusResponse (200)
  → ErrorResponse (404/401)

GET /api/v1/health
  → HealthResponse (200)

GET /api/v1/metrics
  Headers: X-API-Key
  → MetricsResponse (200)

# ── WebSocket Endpoints ─────────────────────────────────────

WS /ws/v1/executions/{execution_id}/events
  Query: ?api_key=<key>
  → Stream of execution events (JSON per message)
  → Closed on execution completion or client disconnect
```

### 5. `__init__.py` — Package Exports

```python
from runtime.kitematic_runtime.api.schemas import (
    IntentRequest, ExecutionResponse, ExecutionStatusResponse,
    ErrorResponse, HealthResponse, MetricsResponse,
)
from runtime.kitematic_runtime.api.auth import (
    AuthProvider, APIKeyAuthProvider, AuthContext, get_auth_context,
)
from runtime.kitematic_runtime.api.events import EventPublisher
from runtime.kitematic_runtime.api.app import create_app
```

## Test Plan

### `test_api_schemas.py` (~10 tests)
- IntentRequest: valid construction, missing required fields, defaults
- ExecutionResponse: construction, serialization roundtrip
- ErrorResponse: construction with code
- HealthResponse: construction
- MetricsResponse: construction with all metric types
- Pydantic validation: extra fields rejected, types enforced

### `test_api_auth.py` (~8 tests)
- APIKeyAuthProvider: valid key → AuthContext
- APIKeyAuthProvider: invalid key → None
- APIKeyAuthProvider: empty key → None
- APIKeyAuthProvider: multiple keys
- get_auth_context dependency: valid request passes
- get_auth_context dependency: missing header → 401
- get_auth_context dependency: invalid key → 401
- AuthContext: permissions list default

### `test_api_events.py` (~8 tests)
- subscribe returns a queue
- publish delivers to subscribers
- unsubscribe removes subscriber
- close sends sentinel and clears
- multiple subscribers for same execution
- multiple executions isolated
- subscribe after close is fresh
- queue receives events in order

### `test_api_routes.py` (~12 tests, using TestClient)
- POST /api/v1/intents: happy path → 201 + ExecutionResponse
- POST /api/v1/intents: missing X-API-Key → 401
- POST /api/v1/intents: invalid key → 401
- POST /api/v1/intents: invalid body → 422
- POST /api/v1/intents: policy rejection → 200 + success=false
- POST /api/v1/intents: tenant context propagation
- GET /api/v1/executions/{id}: existing execution → 200
- GET /api/v1/executions/{id}: unknown execution → 404
- GET /api/v1/health: → 200 + status=ok
- GET /api/v1/metrics: → 200 + metrics data
- Error responses have correct ErrorResponse format
- Tenant headers propagated to runtime

### `test_api_websocket.py` (~6 tests)
- WebSocket connect with valid key → connected
- WebSocket connect without key → rejected (4001)
- WebSocket connect with invalid key → rejected (4001)
- Receive events after intent execution
- Client disconnect doesn't affect runtime
- Multiple clients for same execution

## Implementation Order

1. **schemas.py** + **test_api_schemas.py** — Contracts first (no dependencies)
2. **auth.py** + **test_api_auth.py** — Auth middleware (depends on schemas)
3. **events.py** + **test_api_events.py** — Event publisher (no dependencies)
4. **app.py** + **test_api_routes.py** — Routes + TestClient (depends on all above)
5. **test_api_websocket.py** — WebSocket tests (depends on app + events)
6. **__init__.py** — Package exports
7. **Run full test suite** — Verify all 324+ tests pass

## Architectural Invariants Preserved

- **Intelligence ≠ Authority**: API layer validates format, not meaning
- **Runtime First**: API is a transport boundary, not an execution layer
- **Gateway Chain**: API never accesses tools directly
- **Tenant Isolation**: API propagates context, IsolationBoundary enforces
- **No Direct Agent Tool Access**: Agents submit Intents via API, tools go through Gateway
- **Zero-Trust**: Every request authenticated, every execution validated

## Expected Test Count

- Existing: 324 tests
- New: ~44 tests (10 + 8 + 8 + 12 + 6)
- **Total: ~368 tests**

## Verification

After implementation:
1. Run full test suite: `python -m pytest runtime/ tests/runtime/ -v`
2. Verify all tests pass with 0 failures
3. Verify no regressions in existing P1 + P2 tests
4. Check FastAPI app starts: `python -c "from runtime.kitematic_runtime.api import create_app; print('OK')"`
