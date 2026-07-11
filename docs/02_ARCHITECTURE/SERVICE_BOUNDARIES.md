# Kitematic Service Boundaries

Defines the **service decomposition**, **data ownership**, and **communication rules** for the Kitematic Control Plane.

## Service Map

| Service | Responsibility | Data Ownership | Communicates With |
|---------|---------------|----------------|-------------------|
| **API Gateway** | External auth, rate limiting, request routing | None (stateless) | All Control Plane services |
| **Agent Registry** | Agent templates, manifests, versioning, compatibility | `agent_templates`, `agent_instances`, `agent_manifests` | Orchestrator, Lifecycle Manager |
| **Lifecycle Manager** | Start, stop, pause, resume, scale, upgrade | `executions` (status only) | Orchestrator, Worker Pool |
| **Orchestrator** | State machine, step coordination, checkpoint triggers | None (transient state in Redis) | All services |
| **Policy Engine** | Authorization evaluation, compliance enforcement | `policies`, `policy_rules`, `audit_logs` | Orchestrator, MCP Gateway, Model Gateway |
| **MCP Gateway** | Tool discovery, capability negotiation, permission enforcement | `mcp_servers`, `tools` | Orchestrator, Policy Engine, External MCP Servers |
| **Model Gateway** | LLM routing, cost control, fallback, privacy routing | `llm_providers`, token usage logs | Orchestrator, Policy Engine, LLM APIs |
| **Memory Service** | Short-term, long-term, RAG memory management | `memory_items` (metadata), Redis, Vector DB | Orchestrator |
| **Checkpoint Service** | Snapshot, restore, replay, fork | `checkpoints`, Object Storage | Orchestrator |
| **Human Approval Service** | HITL request management | `approval_requests` | Orchestrator, API Gateway |
| **Observability Service** | Metrics, tracing, logging, cost tracking | Time-series DB, logs | All services (reads only) |
| **Secret Manager** | Secure storage and injection of secrets | Encrypted secret store | All services (reads only) |

## Layer Isolation Rules

### Control Plane Services
- May communicate with each other via **gRPC** only.
- No service may access another service's database directly — all access must be through the owning service's API.

### Execution Plane (Workers)
- **MUST NOT** connect to any database directly.
- **MUST NOT** make external network calls — all external access via MCP Gateway.
- **MUST NOT** store persistent state — only ephemeral working state.
- May only communicate with: Orchestrator (gRPC), MCP Gateway (gRPC), Model Gateway (gRPC).

### Data Plane
- Databases are **owned** by exactly one service.
- Other services access data only through the owning service's API.

## Data Ownership Matrix

| Table | Owner Service | Access Pattern |
|-------|---------------|----------------|
| `tenants`, `workspaces`, `users` | API Gateway / IAM Service | CRUD via REST |
| `agent_templates`, `agent_instances` | Agent Registry | CRUD via gRPC |
| `executions` | Lifecycle Manager | Orchestrator reads/writes via gRPC |
| `policies`, `policy_rules` | Policy Engine | CRUD via gRPC |
| `audit_logs` | Policy Engine | Append-only via gRPC |
| `mcp_servers`, `tools` | MCP Gateway | CRUD via gRPC |
| `llm_providers` | Model Gateway | CRUD via gRPC |
| `memory_items` | Memory Service | CRUD via gRPC |
| `checkpoints` | Checkpoint Service | CRUD via gRPC, blobs in Object Storage |
| `approval_requests` | Human Approval Service | CRUD via REST/gRPC |
| `adapters`, `adapter_capabilities` | Adapter Manager | CRUD via gRPC |
| `marketplace_packages` | Marketplace Service | CRUD via REST |

## Network Policy Rules

| From | To | Protocol | Port | Purpose |
|------|----|----------|------|---------|
| API Gateway | All Control Plane | gRPC | 50051+ | Internal routing |
| Orchestrator | All Control Plane | gRPC | 50051+ | Step coordination |
| Worker | Orchestrator | gRPC | 50051 | Task assignment |
| Worker | MCP Gateway | gRPC | 50052 | Tool execution requests |
| Worker | Model Gateway | gRPC | 50053 | LLM inference requests |
| MCP Gateway | External MCP Servers | HTTPS | 443 | Tool execution (policy-permitted) |
| Model Gateway | External LLM APIs | HTTPS | 443 | Model inference (policy-permitted) |
| All | Secret Manager | gRPC | 50056 | Secret retrieval |

## Forbidden Communication Patterns

- ❌ Worker → Database (any)
- ❌ Worker → External Internet (must go through MCP Gateway)
- ❌ Service A → Service B's database (must go through Service B's API)
- ❌ API Gateway → Worker (must go through Orchestrator)
- ❌ External Client → Internal services (must go through API Gateway)
