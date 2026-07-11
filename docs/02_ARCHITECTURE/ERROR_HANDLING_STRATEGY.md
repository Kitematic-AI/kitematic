# Kitematic Error Handling Strategy

Unified approach to error classification, retry policies, circuit breakers, and dead letter queues.

---

## 1. Error Classification

Every error in the system belongs to exactly one category:

| Category | Recoverable | Examples |
|----------|-------------|---------|
| **TRANSIENT** | Yes — retry likely succeeds | Network timeout, database connection pool exhaustion, rate limit exceeded |
| **POLICY** | No — retry will fail | Action denied by policy, budget exceeded, tool not in allowlist |
| **CONFIGURATION** | No — requires human fix | Adapter version mismatch, missing secret, invalid manifest |
| **RESOURCE_EXHAUSTED** | Maybe — wait and retry | GPU OOM, disk full, token limit exceeded |
| **INTERNAL** | Maybe — retry may help | Unexpected exception, service unavailable, data corruption |
| **FATAL** | No — Agent must stop | Constitution violation detected, checkpoint hash mismatch |

---

## 2. Error Response Schema (gRPC)

```protobuf
message ErrorDetails {
  string error_id = 1;          // Unique error identifier (uuid)
  string category = 2;          // TRANSIENT, POLICY, CONFIGURATION, RESOURCE_EXHAUSTED, INTERNAL, FATAL
  string code = 3;              // Machine-readable error code (e.g., "POLICY_DENIED")
  string message = 4;           // Human-readable description
  bool recoverable = 5;         // Can this error be resolved by retrying?
  string recommended_action = 6; // "retry", "retry_delayed", "contact_admin", "abort"
  map<string, string> details = 7; // Additional context
}
```

---

## 3. Retry Policy

### Transient Errors
| Attempt | Delay | Notes |
|---------|-------|-------|
| 1 | 100ms | Immediate retry |
| 2 | 500ms | Short backoff |
| 3 | 2s | Medium backoff |
| 4 | 5s | Long backoff |
| 5+ | Exponential (5s → 60s max) | Cap at 60s |

After 3 failed attempts → emit `error.escalated` event.
After 5 failed attempts → circuit breaker opens for this resource.

### Resource Exhausted Errors
| Attempt | Delay | Notes |
|---------|-------|-------|
| 1 | 5s | Wait for resource to free |
| 2 | 30s | Longer wait |
| 3 | 120s | Max delay before escalation |

### Policy, Configuration, and Fatal Errors
**No retry.** Return error immediately with full details.

---

## 4. Circuit Breaker Pattern

Each external dependency (MCP Server, LLM Provider, Database) gets its own circuit breaker.

### States
```
CLOSED (normal operation)
   │ 5+ consecutive failures
   ▼
OPEN (reject requests immediately)
   │ timeout (default: 30s)
   ▼
HALF_OPEN (probe with 1 request)
   │ success → CLOSED
   │ failure → OPEN (restart timeout)
```

### Circuit Breaker Configuration
| Dependency | Failure Threshold | Timeout | Notes |
|-----------|-------------------|---------|-------|
| MCP Server | 5 | 30s | Per server |
| LLM Provider | 3 | 60s | Per model endpoint |
| PostgreSQL | 3 | 15s | Cluster-level |
| Redis | 3 | 10s | Cluster-level |

### Events
- `circuit.opened` — dependency_name, failure_count
- `circuit.half_opened` — dependency_name
- `circuit.closed` — dependency_name

---

## 5. Dead Letter Queue (DLQ)

Events that fail to process after exhausting all retries are sent to a Dead Letter Queue.

### DLQ Entry Schema
```json
{
  "dlq_id": "dlq_001",
  "original_event_id": "evt_123",
  "original_event_type": "tool.execute",
  "failure_reason": "MCP_SERVER_UNREACHABLE",
  "retry_attempts": 5,
  "first_failure_at": "2026-07-11T10:00:00Z",
  "last_failure_at": "2026-07-11T10:05:00Z",
  "payload": { ... }
}
```

### DLQ Processing
- Human operator reviews DLQ entries.
- Options: "Retry", "Discard", "Forward to support ticket".
- DLQ entries older than 30 days are automatically discarded.

---

## 6. Graceful Degradation

When a non-critical service is unavailable, the system degrades gracefully rather than failing entirely.

| Unavailable Service | Degradation | Notes |
|--------------------|-------------|-------|
| Observability | Continue execution, buffer logs locally | Batch-send when restored |
| Memory Service | Continue without long-term memory | Short-term memory (Redis) still works |
| Approval Service | Default to DENY for REQUIRES_APPROVAL actions | Fail secure |
| MCP Server (single) | Fallback to alternative server if available | Log the failure |
| LLM Provider (single) | Route to alternative provider | Log the fallback |

---

## 7. Error Logging Standards

Every error must produce an audit log entry with:
- `error_id` (traceable across services)
- `category` (for automated analysis)
- `service` + `function` (for debugging)
- `execution_id` + `agent_id` (for business context)
- `stack_trace` (truncated to 10 frames, secrets redacted)
