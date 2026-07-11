# Kitematic Event Model

Defines all event types, schemas, and topics for the Event Bus.

## 1. Event Envelope

Every event follows this standard structure:

```json
{
  "event_id": "evt_123456",
  "event_type": "agent.step.completed",
  "timestamp": "2026-01-01T10:00:00Z",
  "source": "worker-node-1",
  "version": "v1",
  "tenant_id": "tenant_abc",
  "workspace_id": "workspace_xyz",
  "correlation_id": "exec_98765",
  "payload": {}
}
```

## 2. Event Topics

### Agent Lifecycle Events

| Event Type | Source | Description |
|-----------|--------|-------------|
| `agent.created` | Agent Registry | New Agent instance registered |
| `agent.updated` | Agent Registry | Agent configuration changed |
| `agent.deleted` | Agent Registry | Agent archived |
| `agent.started` | Lifecycle Manager | Execution began |
| `agent.step.completed` | Worker | One step finished |
| `agent.paused` | Orchestrator | Execution paused (HITL or manual) |
| `agent.resumed` | Orchestrator | Execution resumed |
| `agent.completed` | Worker | Agent reached goal |
| `agent.failed` | Worker | Irrecoverable error |
| `agent.cost.updated` | Observability | Token/cost metrics updated |

### Tool Events

| Event Type | Source | Description |
|-----------|--------|-------------|
| `tool.requested` | MCP Gateway | Tool execution requested |
| `tool.approved` | Policy Engine | Tool execution allowed |
| `tool.denied` | Policy Engine | Tool execution rejected |
| `tool.completed` | MCP Gateway | Tool execution finished |
| `tool.failed` | MCP Gateway | Tool execution error |

### Security Events

| Event Type | Source | Description |
|-----------|--------|-------------|
| `policy.denied` | Policy Engine | Action blocked by policy |
| `approval.requested` | Approval Service | HITL approval needed |
| `approval.approved` | Approval Service | Human approved |
| `approval.rejected` | Approval Service | Human rejected |
| `secret.accessed` | Secret Manager | Secret retrieved (metadata only) |

### Memory Events

| Event Type | Source | Description |
|-----------|--------|-------------|
| `memory.created` | Memory Service | New memory item stored |
| `memory.updated` | Memory Service | Memory confidence updated |
| `memory.deleted` | Memory Service | Memory expired or removed |
| `checkpoint.created` | Checkpoint Service | New checkpoint saved |
| `checkpoint.restored` | Checkpoint Service | Execution restored from checkpoint |

### Infrastructure Events

| Event Type | Source | Description |
|-----------|--------|-------------|
| `worker.registered` | Worker Pool | New worker joined |
| `worker.offline` | Worker Pool | Worker disconnected |
| `worker.capacity.changed` | Worker Pool | Available capacity changed |

## 3. Event Bus Architecture

### MVP Phase (Phase 2-3)
- **Technology:** Redis Streams.
- **Retention:** 7 days.
- **Consumer Groups:** One per service.

### Enterprise Phase (Phase 6+)
- **Technology:** Apache Kafka.
- **Retention:** Configurable (up to 90 days).
- **Partitioning:** By `tenant_id`.
- **Replication Factor:** 3.

### Schema Registry
- All event schemas are versioned in a Schema Registry.
- Producers and consumers must agree on schema version.
- Backward-compatible schema evolution enforced.
