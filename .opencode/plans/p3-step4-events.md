# P3 Step 4: Distributed Events — Plan

**Goal:** Extract `EventPublisher` ABC so the runtime and API don't know whether events are delivered via in-memory queues or Redis Pub/Sub. The existing `EventPublisher` (concrete) becomes `InMemoryEventPublisher` under a new `EventPublisher` protocol.

---

## 5 Phases

### Phase 1: Event Models (5 min)

Create `runtime/kitematic_runtime/events/` (new package — separate from `api/events.py`).

```python
# runtime/kitematic_runtime/events/models.py

@dataclass(frozen=True)
class ExecutionEvent:
    """Immutable event envelope for all runtime events."""
    event_id: str
    execution_id: str
    tenant_id: str
    event_type: str
    payload: dict[str, Any]
    timestamp: datetime
    schema_version: int = 1
```

This is a **value object** — frozen, serializable, versioned. The current `api/events.py` publishes raw `dict`s; this formalizes the contract. The EventLog (source of truth) remains unchanged.

### Phase 2: EventPublisher ABC (10 min)

Create `runtime/kitematic_runtime/events/protocol.py`:

```python
class EventPublisher(ABC):
    @abstractmethod
    async def publish(self, event: ExecutionEvent) -> None: ...

    @abstractmethod
    def subscribe(self, execution_id: str) -> asyncio.Queue: ...

    @abstractmethod
    def unsubscribe(self, execution_id: str, queue: asyncio.Queue) -> None: ...

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

### Phase 3: Rename Current Implementation (10 min)

- `api/events.py`: `EventPublisher` → `InMemoryEventPublisher` (all internals stay)
- `api/events.py`: Add `EventPublisher = InMemoryEventPublisher` alias for backward compat
- Update `api/app.py` references (change type hints from concrete to ABC)
- Update `api/__init__.py` exports (add `InMemoryEventPublisher`, keep `EventPublisher` alias)

No behavior change. All existing tests pass unchanged.

### Phase 4: Redis Implementation (15 min)

Create `runtime/kitematic_runtime/events/redis_publisher.py`:

```python
class RedisEventPublisher(EventPublisher):
    def __init__(self, redis_url: str, channel_prefix: str = "kitematic"):
        self._redis = ...
        self._local_queues: dict[str, list[asyncio.Queue]] = {}
    
    async def publish(self, event: ExecutionEvent) -> None:
        # Publish to Redis channel: kitematic:events:{execution_id}
        # Also deliver to local subscribers
        ...
```

**Note:** `redis` is not installed. The implementation will be defined and type-checked but requires `pip install redis` to test. Tests will be written with a skip-if-unavailable decorator.

### Phase 5: Configuration Integration (5 min)

Extend `RuntimeSettings` (from P3.3) with:

```python
class RuntimeSettings(BaseSettings):
    ...
    # Events (P3.4)
    event_backend: str = Field(default="memory")
    redis_url: str | None = Field(default=None)
    event_channel_prefix: str = Field(default="kitematic")

    @field_validator("event_backend")
    @classmethod
    def validate_event_backend(cls, value: str) -> str:
        allowed = {"memory", "redis"}
        if value.lower() not in allowed:
            raise ValueError(f"event_backend must be one of: {allowed}")
        return value.lower()
```

Factory function in `events/protocol.py`:

```python
def create_event_publisher(settings: RuntimeSettings) -> EventPublisher:
    if settings.event_backend == "redis":
        if not settings.redis_url:
            raise ValueError("redis_url required when event_backend=redis")
        return RedisEventPublisher(settings.redis_url, settings.event_channel_prefix)
    return InMemoryEventPublisher()
```

---

## Test Plan (~30 tests)

| Category | Count | What |
|----------|-------|------|
| **Event model** | 3 | immutable, serialization, schema_version |
| **EventPublisher ABC** | 2 | cannot instantiate ABC, all methods defined |
| **InMemoryEventPublisher** | 8 | publish, subscribe, multiple subs, close, close_all, subscriber_count (reuse existing tests) |
| **RedisEventPublisher** | 4 | importable, constructor works, raises without redis, skipped if unavailable |
| **Factory** | 4 | creates correct type for memory, raises for invalid backend, requires redis_url for redis |
| **Configuration** | 3 | event_backend validates, redis_url parsed, channel_prefix defaults |
| **Backward compat** | 3 | old EventPublisher import still works, runtime without events unchanged |
| **Integration** | 3 | app with InMemoryEventPublisher, app with RedisEventPublisher (skip if no redis) |
| **Total** | **~30** | |

---

## Test Count Impact

```
Before P3.4:    455 tests
New:            +30 tests
After P3.4:     485 tests (estimated), 0 failures
```

---

## What Is NOT in Scope

| Excluded | Reason |
|----------|--------|
| Kafka / NATS | Not needed; Redis covers the distributed gap |
| Event persistence | EventLog is already the source of truth |
| Replay system | Already documented: "replay from EventLog on reconnect" |
| Exactly-once delivery | WebSocket semantics; at-least-once is sufficient |
| Distributed tracing across events | P4 concern |
| Event versioning / migration | schema_version=1 is reserved but not migrated |

---

## Key Design Decisions

1. **New `events/` package** — separate from `api/events.py` to keep transport concerns out of the runtime core
2. **Backward compat alias** — `EventPublisher = InMemoryEventPublisher` so no imports break
3. **Redis is optional** — implementation defined but `pip install redis` required for tests
4. **Factory pattern** — `create_event_publisher(settings)` hides implementation choice
5. **ExecutionEvent is frozen** — matches the immutability invariants of the rest of the codebase

---

## Execution Order

```
Phase 1: Event models  →  Phase 2: ABC  →  Phase 3: Rename  →  Phase 4: Redis  →  Phase 5: Config
```

Each phase builds on the previous. Tests are written alongside each phase.
