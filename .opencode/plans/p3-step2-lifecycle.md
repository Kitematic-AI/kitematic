# P3 Step 2: Lifecycle Hardening — Plan

**Goal:** Graceful startup, shutdown, and resource cleanup across Runtime, Loop, EventPublisher, and FastAPI.

---

## Changes

### 1. `runtime.py` — `KitematicRuntime.stop()`

Add a `_stopping` flag and an async `stop()` method.

```python
# In __init__:
self._stopping: bool = False

# New method:
async def stop(self) -> None:
    """Gracefully stop the runtime.
    
    Sets a flag that prevents new executions.
    In-flight executions are NOT interrupted (runtime is stateless —
    they will complete naturally).
    """
    self._stopping = True
    if self._logger:
        self._logger.info("Runtime shutting down")
```

At the start of `execute_intent()`, before any work:
```python
if self._stopping:
    return ExecutionResult(
        success=False,
        execution_id=execution_id,
        error="Runtime is shutting down",
        state=ExecutionState.CREATED,
    )
```

**Why no in-flight tracking:** The runtime is a pure execution engine — it doesn't hold async tasks. In-flight executions are managed by the caller (LoopController or API layer). `stop()` only rejects new work.

### 2. `loop.py` — `LoopController.shutdown()`

```python
async def shutdown(self, timeout_seconds: float = 30.0) -> None:
    """Shutdown the loop controller, preventing new intents."""
    self._stopping = True
    if self._logger:
        self._logger.info("Loop shutting down", timeout_seconds=timeout_seconds)
```

At the start of `run_intent()`:
```python
if getattr(self, "_stopping", False):
    ...return LoopResult(success=False, termination_reason=LoopTermination.EXCEPTION, error="Loop is shutting down")
```

### 3. `api/events.py` — `EventPublisher.close_all()`

```python
def close_all(self) -> None:
    """Close all subscribers across all executions.
    
    Sends None sentinel to every active queue,
    then clears the entire subscriber map.
    """
    for execution_id in list(self._subscribers.keys()):
        self.close(execution_id)
```

This reuses the existing `close(execution_id)` which already sends None and clears.

### 4. `api/app.py` — FastAPI lifespan

```python
from contextlib import asynccontextmanager

# Inside create_app(), before FastAPI instantiation:
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.startup_time = datetime.now(timezone.utc)
    if hasattr(runtime, '_logger') and runtime._logger:
        runtime._logger.info("API starting", version="0.2.0")
    yield
    # Shutdown
    if hasattr(runtime, '_logger') and runtime._logger:
        runtime._logger.info("API shutting down")
    await runtime.stop()
    event_publisher.close_all()

# FastAPI constructor:
app = FastAPI(
    title="Kitematic Runtime API",
    version="0.2.0",
    lifespan=lifespan,
)
```

The lifespan closure captures `runtime` and `event_publisher` from `create_app()` scope.

### 5. `__init__.py` — No changes needed

All new APIs are methods on existing classes. No new exports required.

---

## Test Plan

New file: `tests/runtime/test_kitematic_runtime/test_lifecycle.py` (~10 tests)

### TestRuntimeStop

| # | Test | What it proves |
|---|------|---------------|
| 1 | `test_stop_sets_stopping_flag` | `_stopping` is True after `stop()` |
| 2 | `test_stop_prevents_new_executions` | `execute_intent()` returns failure after `stop()` |
| 3 | `test_stop_error_message` | Error message contains "shutting down" |
| 4 | `test_stop_with_observability_logs_shutdown` | Logger emits "Runtime shutting down" |
| 5 | `test_stop_without_observability_works` | `stop()` works when logger is None |

### TestEventPublisherCloseAll

| # | Test | What it proves |
|---|------|---------------|
| 6 | `test_close_all_clears_all_subscribers` | After close_all(), subscriber_count is 0 for all executions |
| 7 | `test_close_all_sends_sentinels` | Queues receive None after close_all() |
| 8 | `test_close_all_empty_is_noop` | close_all() with no subscribers doesn't raise |

### TestLoopShutdown

| # | Test | What it proves |
|---|------|---------------|
| 9 | `test_loop_shutdown_prevents_new_intents` | `run_intent()` returns failure after `shutdown()` |

### TestFastAPILifecycle

| # | Test | What it proves |
|---|------|---------------|
| 10 | `test_lifespan_startup_sets_time` | `app.state.startup_time` is set after startup |
| 11 | `test_lifespan_shutdown_calls_stop` | `runtime.stop()` is called during shutdown |

---

## Test Count Impact

```
After P3.1:     422 tests
New (lifecycle): +11 tests
After P3.2:     433 tests
```

---

## Execution Notes

- All changes are backward-compatible (new optional behavior, no signature changes)
- `stop()` is idempotent — calling it multiple times is safe
- `close_all()` is idempotent — already handled by `close(execution_id)` pattern
- FastAPI lifespan is the standard pattern for FastAPI >= 0.93
- No new imports required beyond `contextlib.asynccontextmanager` in app.py
