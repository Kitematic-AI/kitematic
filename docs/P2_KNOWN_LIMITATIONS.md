# P2 Known Limitations

**Phase:** P2 — Runtime Integration & Production Readiness
**Date:** 2026-07-24
**Status:** DOCUMENTED (deferred to P3)

---

This document catalogs all known production-readiness gaps identified during
P2 Step 7 (Validation & Architecture Review). These are **intentional deferrals**
— each item represents a conscious decision to cap P2 scope and address the
capability in P3.

---

## 1. Observability Modules: Defined, Not Wired

**Modules affected:** RuntimeLogger, ExecutionTracer, MetricsRegistry (core)

| Module | Status | Tests | Wired In |
|--------|--------|:-----:|----------|
| RuntimeLogger | Defined + tested | 10 | Nowhere |
| ExecutionTracer | Defined + tested | 15 | Nowhere |
| MetricsRegistry (core) | Defined + tested | 13 | API layer only (3 counters) |

**Impact:** All observability data exists but is not emitted during execution.
- No log lines written during `execute_intent()`, `LoopController.run_intent()`, or `MCPToolGateway.access_tool()`.
- No trace phases recorded during execution lifecycle.
- No execution latency or error-rate histograms in the runtime core.

**P3 Plan:** Wire RuntimeLogger into runtime.py (trace-level per step), wire ExecutionTracer into LoopController.run_intent(), wire MetricsRegistry counters/histograms into runtime.py and gateway.py.

---

## 2. EventPublisher: In-Memory Only

**Module:** `api/events.py`

**Current behavior:**
- Subscribers registered per execution in a Python dict
- Events delivered via `asyncio.Queue` (in-process only)
- No persistence of delivered events
- No reconnect support for dropped WebSocket clients
- No multi-process or horizontal scaling

**Impact:**
- Clients that disconnect mid-stream lose all events (must replay from EventLog)
- Cannot run multiple API workers (events are worker-local)
- Not suitable for production deployments with >1 instance

**P3 Plan:** Replace with Redis pub/sub, NATS, or similar distributed event broker. Add reconnect with sequence-number based replay from EventLog.

---

## 3. Graceful Shutdown

**Current behavior:**
- No `SIGTERM`/`SIGINT` handlers in the runtime
- No `stop()` / `close()` methods on KitematicRuntime
- No drain logic for in-flight executions
- No MCP client connection cleanup
- No pending log/metric flush on shutdown

**Impact:**
- `kill <pid>` may leave partial checkpoints, orphaned executions
- MCP connections may hang on the server side
- In-flight metrics counters lost

**P3 Plan:** Add Application lifecycle with startup/shutdown hooks (`atexit`, signal handlers, ASGI lifespan). `KitematicRuntime.stop()` drains in-flight executions, closes MCP clients, flushes pending observability data.

---

## 4. Configuration Management

**Current behavior:**
- All defaults are hardcoded dataclass values:
  - `ExecutionBudget.max_steps = 10`, `max_tokens = 100000`, `timeout_seconds = 3600`
  - `RuntimeLogger` hardcoded to `logging.INFO`, `sys.stdout`
- No env var reading, no YAML/TOML parsing, no config file loading
- `create_app()` accepts all params via constructor injection — no external source

**Impact:**
- Cannot change budget limits without code changes
- Cannot configure log level, output destination, or format from deployment environment
- Cannot configure API key store from environment variables

**P3 Plan:** Add `Settings` model (pydantic-settings). Load from env vars with `.env` fallback. Wire into `create_app()`, `ExecutionBudget`, `RuntimeLogger`.

---

## 5. Dependency Pinning

**Current behavior:**
- No `requirements.txt`, `pyproject.toml`, or `setup.py` in the repository
- Dependencies (fastapi, pydantic, httpx) are unpinned
- No lockfile (pip freeze, poetry.lock, etc.)

**Impact:**
- Breaks may occur when new dependency versions are published
- Reproducible builds are not guaranteed
- CI/CD pipelines may get different versions than local development

**P3 Plan:** Create `pyproject.toml` with pinned core deps, dev deps, and optional extras. Generate lockfile. Document install instructions.

---

## 6. WebSocket Authentication: Query Parameter

**Module:** `api/app.py`

**Current behavior:**
- WebSocket auth uses `?api_key=<key>` query parameter
- Documented as temporary in the handler docstring

**Rationale:** Browser WebSocket API does not support custom headers natively,
making `X-API-Key` header-based auth impossible from browser contexts.

**P3 Plan:** Upgrade to `Sec-WebSocket-Protocol: api-key,<token>` header pattern, or
cookie-based session auth.

---

## 7. `_classify_failure()`: String Matching

**Module:** `loop.py` (method `_classify_failure`, lines 327-352)

**Current behavior:** Classifies loop termination reasons by checking if
error strings contain keywords like `"policy"`, `"capability"`, `"gateway"`.

**Impact:** Fragile — if error message wording changes, classification may
produce incorrect `LoopTermination` values.

**P3 Plan:** Replace with typed exception matching using the `RuntimeContractError.code`
field, or add a `LoopTermination` field to exception classes directly.

---

## 8. MetricsRegistry: Single-Threaded

**Module:** `observability/metrics.py`

**Current behavior:**
- Docstring states "thread-safe for single-threaded use"
- Uses plain `dict` and `defaultdict` with no locks
- Not safe for multi-worker ASGI deployments

**Impact:** Under concurrent request load, counter increments may be lost,
histogram values may be corrupted.

**P3 Plan:** Replace with atomic operations or switch to a production metrics
library (prometheus_client, opentelemetry). Add thread-safe wrappers.

---

## 9. OpenAPI Spec: Not Verified in Tests

**Current behavior:**
- FastAPI auto-generates OpenAPI spec at `/openapi.json`
- No test reads or validates the spec

**Impact:** Spec changes are not caught by CI. Contract changes for API consumers
may go unnoticed.

**P3 Plan:** Add test that fetches `/openapi.json` and validates endpoint routes,
request schemas, and response schemas match expected contracts.
