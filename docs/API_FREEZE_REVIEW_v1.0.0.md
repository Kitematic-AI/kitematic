# API Freeze Review — v1.0.0

## Endpoint Inventory

| # | Method | Path | Auth Required | Stable |
|---|---|---|---|---|
| 1 | POST | `/api/v1/intents` | Yes (X-API-Key) | ✅ |
| 2 | GET | `/api/v1/executions/{execution_id}` | Yes (X-API-Key) | ✅ |
| 3 | GET | `/api/v1/health` | No | ✅ |
| 4 | GET | `/api/v1/metrics` | Yes (X-API-Key) | ✅ |
| 5 | WS | `/ws/v1/executions/{execution_id}/events` | Yes (Bearer / Protocol / query param) | ✅ (query param deprecated) |

## Request Schemas

| Schema | Fields | Stability |
|---|---|---|
| `IntentRequest` | `agent_id: str`, `action: str`, `parameters: dict` | ✅ Stable |
| `TenantHeaders` | `tenant_id: str`, `agent_id: str` | ✅ Stable |

## Response Schemas

| Schema | Fields | Stability |
|---|---|---|
| `ExecutionResponse` | `execution_id`, `success`, `state`, `checkpoint_id`, `data`, `error` | ✅ Stable |
| `ExecutionStatusResponse` | `execution_id`, `state`, `agent_id`, `action`, `success`, `error` | ✅ Stable |
| `ErrorResponse` | `error`, `code`, `details` | ✅ Stable |
| `HealthResponse` | `status`, `version`, `runtime` | ✅ Stable |
| `MetricsResponse` | `counters`, `histograms`, `gauges` | ✅ Stable |

## Authentication

| Method | Mechanism | Status |
|---|---|---|
| REST | `X-API-Key` header → SHA-256 fingerprint → `AuthContext` | ✅ Stable |
| WebSocket | `Authorization: Bearer <key>` (preferred) | ✅ Stable |
| WebSocket | `Sec-WebSocket-Protocol: kitematic.<key>` | ✅ Stable |
| WebSocket | `api_key` query param | ⚠️ Deprecated (v1.1 removal target) |

## Stability Guarantees

For v1.0.0:
- All 5 endpoints above are frozen for the v1.x lifecycle
- Field names, types, and semantics will not change in v1.x
- New fields may be added (backward-compatible) in v1.x minor releases
- The deprecated `api_key` WebSocket query param will be removed in v1.1

## Breaking Changes Checklist

| Check | Status |
|---|---|
| No experimental endpoints in public API | ✅ |
| All field names consistent (snake_case) | ✅ |
| No `Any` types in request models | ✅ |
| All error responses structured | ✅ |
| Health check returns version | ✅ |
| All endpoints versioned under `/api/v1/` | ✅ |
| No internal-only endpoints exposed | ✅ |

## Sign-off

| Role | Date | Signature |
|---|---|---|
| API Reviewer | | |
