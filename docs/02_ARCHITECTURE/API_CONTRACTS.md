# Kitematic API Contracts

Defines all public REST endpoints and internal gRPC services.

## 1. Public REST API

Base URL: `https://api.kitematic.io/v1`
Authentication: Bearer JWT in `Authorization` header.
Multi-tenancy: `X-Tenant-ID` header (required) and `X-Workspace-ID` header (optional).

### Agent Registry & Management

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/templates` | List available Agent templates |
| `POST` | `/agents` | Create a new Agent instance |
| `GET` | `/agents/{id}` | Get Agent details |
| `PATCH` | `/agents/{id}` | Update Agent configuration |
| `DELETE` | `/agents/{id}` | Archive Agent |

### Agent Execution & Lifecycle

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/agents/{id}/runs` | Start a new execution |
| `GET` | `/agents/{id}/runs/{exec}` | Get execution status |
| `POST` | `/agents/{id}/runs/{exec}/pause` | Pause execution |
| `POST` | `/agents/{id}/runs/{exec}/resume` | Resume execution |
| `POST` | `/agents/{id}/runs/{exec}/stop` | Stop execution |

### Time Travel & Checkpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/agents/{id}/runs/{exec}/checkpoints` | List checkpoints |
| `POST` | `/agents/{id}/runs/{exec}/checkpoints/{cp}/fork` | Fork from a checkpoint |

### Human Approvals

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/approvals?status=PENDING` | List pending approvals |
| `GET` | `/approvals/{id}` | Get approval details |
| `POST` | `/approvals/{id}/approve` | Approve a request |
| `POST` | `/approvals/{id}/reject` | Reject a request |

### Governance & Policies

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/policies` | List policies |
| `POST` | `/policies` | Create a policy |
| `PATCH` | `/policies/{id}` | Update a policy |
| `GET` | `/audit-logs` | Query audit logs |
| `POST` | `/mcp-servers` | Register a custom MCP server |

### Observability

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/metrics/costs` | Cost and token usage report |
| `GET` | `/metrics/performance` | Latency and reliability metrics |

### Standard Response Envelope

```json
{
  "status": "success",
  "data": { ... },
  "meta": {
    "request_id": "req_abc123",
    "timestamp": "2026-01-01T10:00:00Z"
  }
}
```

### Error Response

```json
{
  "status": "error",
  "error": {
    "code": "POLICY_DENIED",
    "message": "Action blocked by tenant policy",
    "details": { "policy_id": "pol_456", "rule": "deny_external_email" }
  }
}
```

## 2. Internal gRPC Services

All internal services use gRPC with TLS mutual authentication. Port range: `50051–50059`.

### OrchestratorService

```protobuf
service OrchestratorService {
  rpc ExecuteStep(ExecuteStepRequest) returns (ExecuteStepResponse);
  rpc ResumeExecution(ResumeRequest) returns (ResumeResponse);
  rpc PauseExecution(PauseRequest) returns (PauseResponse);
  rpc HealthCheck(HealthRequest) returns (HealthResponse);
}
```

### MCPGatewayService

```protobuf
service MCPGatewayService {
  rpc DiscoverTools(ToolDiscoveryRequest) returns (ToolList);
  rpc ExecuteTool(ToolExecutionRequest) returns (ToolExecutionResponse);
}
```

### PolicyService

```protobuf
service PolicyService {
  rpc Evaluate(PolicyRequest) returns (PolicyDecision);
  rpc CreatePolicy(PolicyCreateRequest) returns (PolicyResponse);
}
```

### MemoryService

```protobuf
service MemoryService {
  rpc WriteMemory(MemoryWriteRequest) returns (MemoryResponse);
  rpc SearchMemory(MemorySearchRequest) returns (MemoryResults);
  rpc DeleteMemory(MemoryDeleteRequest) returns (MemoryResponse);
}
```

### CheckpointService

```protobuf
service CheckpointService {
  rpc CreateCheckpoint(CheckpointRequest) returns (CheckpointResponse);
  rpc RestoreCheckpoint(RestoreRequest) returns (RestoreResponse);
  rpc ListCheckpoints(CheckpointListRequest) returns (CheckpointListResponse);
}
```

### ModelGatewayService

```protobuf
service ModelGatewayService {
  rpc Generate(ModelRequest) returns (ModelResponse);
  rpc ListModels(ModelListRequest) returns (ModelListResponse);
}
```

### ApprovalService

```protobuf
service ApprovalService {
  rpc RequestApproval(ApprovalRequest) returns (ApprovalResponse);
  rpc Approve(ApproveRequest) returns (ApprovalResponse);
  rpc Reject(RejectRequest) returns (ApprovalResponse);
}
```

## 3. Versioning Policy

- REST API: versioned via URL path (`/v1/`, `/v2/`).
- gRPC: versioned via package name (`kitematic.v1`, `kitematic.v2`).
- Breaking changes require a new version; old version is deprecated over a minimum 6-month window.
- All schema changes must include a migration path in the ADR.
