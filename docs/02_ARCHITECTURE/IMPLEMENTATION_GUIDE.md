# Kitematic Implementation Guide

Ordered execution plan for building Kitematic services, including dependencies, starting point, and acceptance criteria.

---

## 1. Build Order

Services must be built in dependency order. Each service depends on services above it.

```
Priority 1:  Foundation Services
  [1a] API Gateway (auth, routing)
  [1b] Agent Registry (definitions, versioning)
  [1c] Secret Manager (credentials, encryption)

Priority 2:  Core Orchestration
  [2a] Orchestrator (state machine, coordination)
  [2b] Checkpoint Service (snapshot, restore)
  [2c] Memory Service (short/long-term, RAG)

Priority 3:  Governance & Gateways
  [3a] Policy Engine (evaluation, audit)
  [3b] MCP Gateway (tool routing, permissions)
  [3c] Model Gateway (LLM routing, cost control)

Priority 4:  Human Interaction
  [4a] Human Approval Service (HITL)
  [4b] Observability Service (metrics, traces, logs)

Priority 5:  Lifecycle & Scaling
  [5a] Lifecycle Manager (start/stop/scale)
  [5b] Worker Pool Manager (container orchestration)
```

## 2. Starting Point: Agent Registry + API Gateway

### Why start here?
- The Agent Registry holds the core data model (templates, instances, manifests).
- The API Gateway is the entry point — needed before anything else can be tested.
- Together they form the "data plane" for Agent definitions, which everything else depends on.

### Minimum Viable Implementation (Agent Registry)
```python
# Pseudo-code demonstrating the contract
class AgentRegistryService:
    def create_template(self, name, framework, manifest):
        # Validate manifest against RTC schema
        # Store in agent_templates table
        # Return template_id
        pass

    def create_instance(self, template_id, tenant_id, config):
        # Verify template exists and is active
        # Check compatibility of required adapters
        # Store in agent_instances table
        # Return instance_id
        pass

    def get_instance(self, instance_id):
        # Load from agent_instances
        # Join with agent_templates for manifest
        # Return full AgentManifest
        pass
```

### Acceptance Criteria (Agent Registry)
1. Can create a template with a valid manifest
2. Can create an instance from a template
3. Can retrieve full AgentManifest for an instance
4. Incompatible framework is rejected with clear error
5. All operations are isolated by tenant_id (RLS)

## 3. Development Rules

### Coding Standards
- **Language:** Python 3.12+ for MVP (fast iteration), Go for performance-critical paths later
- **Framework:** FastAPI for REST services, grpcio for internal services
- **Database:** psycopg2 + asyncpg for PostgreSQL, redis-py for Redis
- **Testing:** pytest with pytest-asyncio

### Repository Structure
```
services/
├── agent-registry/
│   ├── src/           # Application code
│   ├── tests/         # Unit + integration tests
│   ├── migrations/    # Alembic SQL migrations
│   └── Dockerfile
├── api-gateway/
├── orchestrator/
├── policy-engine/
├── mcp-gateway/
├── model-gateway/
├── memory-service/
├── checkpoint-service/
├── approval-service/
├── observability/
├── lifecycle-manager/
└── secret-manager/
```

### Interface-First Development
1. Define the gRPC proto file first
2. Generate server/client stubs
3. Implement server logic
4. Write integration tests against the proto
5. Once all tests pass, deploy

## 4. Dependencies Between Services

| Service | Depends On | Integration Point |
|---------|-----------|-------------------|
| API Gateway | Agent Registry | gRPC: GetAgent, ValidateToken |
| Orchestrator | Policy Engine | gRPC: Evaluate |
| Orchestrator | Checkpoint Service | gRPC: CreateCheckpoint, RestoreCheckpoint |
| Orchestrator | Memory Service | gRPC: SearchMemory, WriteMemory |
| MCP Gateway | Policy Engine | gRPC: Evaluate |
| MCP Gateway | Secret Manager | gRPC: GetSecret |
| Model Gateway | Policy Engine | gRPC: Evaluate |
| Lifecycle Manager | Orchestrator | gRPC: StartExecution, StopExecution |
| Worker Pool | Orchestrator | gRPC: AssignTask |

## 5. Mocking Strategy for Parallel Development

To allow services to be developed in parallel, provide a **Mock Control Plane** that implements all gRPC interfaces with canned responses:

```python
class MockPolicyEngine:
    def evaluate(self, request):
        return PolicyDecision(decision="ALLOW")

class MockMemoryService:
    def search(self, request):
        return MemoryResults(items=[])
```

These mocks are replaced with real implementations as each service is completed.

## 6. Milestone Gates

| Milestone | Criteria | Est. Effort |
|-----------|----------|-------------|
| M1 | Agent Registry + API Gateway: CRUD for templates and instances | 2 weeks |
| M2 | Orchestrator + Checkpoint: Step execution with save/restore | 3 weeks |
| M3 | Policy Engine + MCP Gateway: Tool execution with governance | 2 weeks |
| M4 | Memory + Model Gateway: RAG and LLM routing | 2 weeks |
| M5 | Approval + Observability: HITL and monitoring | 2 weeks |
| M6 | Lifecycle Manager + Worker Pool: Full execution lifecycle | 2 weeks |

Total estimated time to MVP (M1–M6): **13 weeks** with 2 developers.
