# Kitematic Service Specifications

Detailed internal specifications for each Control Plane service: internal models, algorithms, error handling patterns, and implementation notes.

---

## 1. API Gateway

### Purpose
External entry point. Handles authentication, rate limiting, request validation, and routing to internal services.

### Internal Models

```json
{
  "api_request": {
    "method": "POST",
    "path": "/v1/agents/{id}/runs",
    "headers": { "Authorization": "Bearer <jwt>", "X-Tenant-ID": "..." },
    "body": { "goal": "Analyze sales data" }
  },
  "authenticated_context": {
    "tenant_id": "uuid",
    "user_id": "uuid",
    "workspace_id": "uuid",
    "role": "developer",
    "token_claims": { "scopes": ["agents:write"] }
  }
}
```

### Flow
1. Receive HTTP request → validate TLS → extract JWT → validate signature/expiry
2. Extract tenant_id, user_id, role from JWT claims
3. Rate limit check (per tenant, per endpoint)
4. Route to appropriate internal service via gRPC
5. Return response or stream to client

### Error Handling
- 401: Invalid/expired JWT → detailed error message
- 429: Rate limit exceeded → Retry-After header
- 502: Internal service unavailable → circuit breaker

---

## 2. Agent Registry Service

### Purpose
Store, version, and validate Agent definitions (templates and instances). Resolve compatibility between Agent requirements and available adapters.

### Internal Models

```json
{
  "agent_template": {
    "id": "uuid",
    "name": "financial-analyst",
    "description": "...",
    "framework": "langgraph",
    "manifest": {
      "runtime_contract_version": "1.0",
      "required_adapters": ["salesforce-mcp", "postgres-tool"],
      "allowed_models": ["gpt-4", "claude-3"],
      "max_tokens": 50000
    },
    "security_rating": "T2",
    "creator_type": "system"
  },
  "agent_instance": {
    "id": "uuid",
    "tenant_id": "uuid",
    "template_id": "uuid",
    "name": "Q4-Financial-Analyst",
    "status": "active",
    "deployment_config": {
      "allowed_tools": ["salesforce.read", "postgres.query"],
      "model_routing": { "default": "azure-gpt-4", "fallback": "local-llama" },
      "policy_profile": "finance-strict",
      "budget": { "max_tokens_per_run": 100000, "max_cost_usd": 5.00 }
    }
  }
}
```

### Validation Algorithm
1. Load template manifest → check runtime_contract_version compatibility
2. Verify all required_adapters exist in the Adapter Registry with status=active
3. Verify tenant's policy profile allows the requested model/tool combination
4. If validation fails, return detailed error with which check failed and why

### Versioning
- agent_manifests table stores full JSON snapshot per version
- On update: increment version, keep previous version for rollback
- Rollback: re-deploy agents/{id}/runs with version=X, pointing to old manifest

---

## 3. Orchestrator Service

### Purpose
State machine coordinator. Drives step-by-step Agent execution: policy check → execute → checkpoint → repeat.

### Internal Models

```json
{
  "execution_context": {
    "execution_id": "uuid",
    "agent_instance_id": "uuid",
    "tenant_id": "uuid",
    "status": "running",
    "current_step": {
      "step_number": 5,
      "node_name": "analyze_data",
      "runtime": "langgraph",
      "input_state_hash": "sha256:..."
    },
    "checkpoint_ref": "uuid",
    "memory_context": { "session_id": "redis:exec_123" },
    "budget_consumed": { "tokens": 24500, "cost_usd": 0.48, "time_ms": 34000 }
  }
}
```

### Execution Loop Algorithm
```
1. Orchestrator receives execute_step(execution_id, state) from Lifecycle Manager
2. Save pre-execution checkpoint (checkpoint trigger: BEFORE_STEP)
3. Call Policy Engine → evaluate(agent, action, resource)
4. If DENIED → pause execution, notify user, return
5. If REQUIRE_APPROVAL → create approval_request, pause, return
6. Call Worker → execute_step(state, permissions)
7. Worker returns one of: COMPLETED, TOOL_REQUEST, APPROVAL_REQUIRED, FAILED
8. If TOOL_REQUEST → call MCP Gateway → get result → feed back to Worker
9. If CHECKPOINT_REQUIRED → save checkpoint, continue
10. Save post-execution checkpoint (checkpoint trigger: AFTER_STEP)
11. Update budget consumed → if exceeded, pause
12. Return result to Lifecycle Manager
```

### Error Handling
- Worker timeout (configurable per step, default 120s) → save error checkpoint → retry up to 3 times → mark FAILED
- MCP Gateway unavailable → retry with exponential backoff (100ms, 500ms, 2s)
- Database unavailable → circuit breaker, queue requests

---

## 4. Policy Engine

### Purpose
Evaluate every action request against defined policies. Maintain immutable audit trail.

### Internal Models

```json
{
  "policy_rule": {
    "id": "uuid",
    "tenant_id": "uuid",
    "name": "block-public-llm-for-finance",
    "target": "model.gpt-4",
    "effect": "DENY",
    "condition": "agent.tags contains 'finance'",
    "priority": 100,
    "audit_level": "FULL_PAYLOAD"
  },
  "policy_decision": {
    "request_id": "uuid",
    "decision": "DENY",
    "matched_rule": "block-public-llm-for-finance",
    "reason": "Finance agents cannot use public LLM models",
    "audit_log_ref": "audit_789"
  }
}
```

### Evaluation Algorithm
```
1. Load all active policies for tenant (cached, 5-min TTL)
2. Sort by priority (highest first)
3. For each policy:
   a. Match target against request (supports wildcards: "model.*")
   b. If match, evaluate condition (CEL expression)
   c. If condition passes, return effect (DENY or REQUIRE_APPROVAL)
4. If no deny/approval match, check allow rules same way
5. If no allow match either → DEFAULT_DENY (fail secure)
6. Log every evaluation to audit_logs (append-only)
```

### CEL Condition Examples
```
"request.time.hour < 18"                    // Only allow during business hours
"agent.tags.all(tag, tag in ['approved'])"  // Agent must have approved tag
"resource.size_mb < 10"                     // Limit data extraction size
"user.role in ['admin', 'manager']"         // Role-based tool access
```

---

## 5. MCP Gateway Service

### Purpose
Bridge between Agents and external tools via MCP protocol. Handle discovery, capability negotiation, policy enforcement, and execution.

### Internal Models

```json
{
  "mcp_server": {
    "id": "uuid",
    "name": "github-mcp",
    "url": "https://mcp.github.com/v1",
    "capabilities": ["repository.read", "issue.create", "pr.merge"],
    "auth_type": "oauth2",
    "status": "active"
  },
  "tool_execution_request": {
    "execution_id": "uuid",
    "agent_id": "uuid",
    "mcp_server": "github-mcp",
    "tool": "repository.read",
    "parameters": { "owner": "company", "repo": "project" }
  }
}
```

### Flow
1. Receive tool request from Worker via gRPC
2. Validate tool is in Agent's allowed_tools list
3. Call Policy Engine → evaluate(agent_id, "mcp.github.read", resource)
4. If ALLOWED → execute tool on MCP Server, return result
5. If DENIED → return error, Worker emits TOOL_DENIED event
6. If REQUIRE_APPROVAL → create approval_request, pause execution

### MCP Server Discovery
- On startup and every 5 minutes, call DiscoverTools() on each registered MCP server
- Cache tool list in redis with 5-min TTL
- If MCP server is unreachable, mark as degraded, alert operator

---

## 6. Memory Service

### Purpose
Centralized memory management. Short-term (Redis), Working (Redis+PG), Long-term (Vector DB), Enterprise Knowledge (RAG).

### Internal Models

```json
{
  "memory_item": {
    "id": "uuid",
    "tenant_id": "uuid",
    "instance_id": "uuid",
    "type": "FACT",
    "content": "Customer prefers email communication",
    "confidence": 0.92,
    "source": "conversation",
    "created_at": "2026-07-11T10:00:00Z",
    "expires_at": "2026-10-11T10:00:00Z"
  }
}
```

### Write Flow
1. Validate memory type and confidence threshold
2. Embed content if type=FACT or EXPERIENCE (Vector DB)
3. Store metadata in PostgreSQL (memory_items table)
4. Store embedding in Vector DB with tenant_id as filter
5. Return memory reference

### Search Flow
1. Parse query → extract search terms
2. Search Vector DB with tenant_id filter (semantic search)
3. Search PostgreSQL with keyword/pattern matching (lexical search)
4. Merge results, rank by confidence_score
5. Return top-K results (configurable, default 10)

---

## 7. Model Gateway Service

### Purpose
Unified LLM interface. Route requests based on cost, privacy, capability, and policy.

### Internal Models

```json
{
  "model_request": {
    "execution_id": "uuid",
    "agent_id": "uuid",
    "task_type": "reasoning",
    "privacy_level": "confidential",
    "max_cost_usd": 0.50,
    "prompt": "...",
    "preferred_providers": ["azure", "local"]
  },
  "model_routing_decision": {
    "selected_provider": "azure-openai",
    "selected_model": "gpt-4",
    "estimated_cost": 0.32,
    "reason": "Confidential data requires Azure; budget allows GPT-4"
  }
}
```

### Routing Algorithm
```
1. Parse model_request → extract requirements (task_type, privacy, max_cost)
2. If privacy == "confidential" or higher → exclude public providers (OpenAI, Anthropic)
3. Filter remaining providers by capability match (task_type)
4. Filter remaining by cost estimate within max_cost_usd
5. Sort by: privacy_match > capability_score > cost (lowest first)
6. Return highest-ranked provider/model
7. If all providers filtered out → return error: NO_COMPATIBLE_MODEL
```

---

## 8. Checkpoint Service

### Purpose
Save and restore execution state. Enable time travel (fork, replay, rollback).

### Internal Models

```json
{
  "checkpoint": {
    "id": "uuid",
    "execution_id": "uuid",
    "version": 12,
    "parent_checkpoint_id": "uuid",
    "trigger_reason": "BEFORE_TOOL_CALL",
    "agent_state": { ... },
    "tool_history": [...],
    "memory_refs": [...],
    "budget_snapshot": { "tokens": 45000, "cost_usd": 0.89 },
    "created_at": "2026-07-11T10:00:00Z"
  }
}
```

### Storage Strategy
- Metadata (without agent_state blob) → PostgreSQL (checkpoints table)
- agent_state blob → Object Storage (S3-compatible), keyed by checkpoint_id
- Total checkpoint retention: 90 days (configurable)
- Snapshot interval: every 5 steps minimum, or on trigger

### Restore Flow
1. Load checkpoint metadata from PostgreSQL
2. Load agent_state from Object Storage
3. Validate integrity (compare checkpoint_hash)
4. Restore execution context in Redis
5. Return restored state to Orchestrator
6. Log restore event to audit_logs
