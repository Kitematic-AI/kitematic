# Kitematic Security Boundaries

Defines network isolation, secrets management, encryption, and access control architecture.

## 1. Network Isolation Zones

```
Internet
    │
    ▼
┌─────────────────────────────────────────────┐
│           Zone 1: DMZ / Public              │
│  API Gateway (TLS termination, auth, rate   │
│  limiting, WAF)                             │
└─────────────────────────────────────────────┘
    │ (internal network, mTLS)
    ▼
┌─────────────────────────────────────────────┐
│           Zone 2: Control Plane             │
│  Orchestrator, Policy Engine, Agent         │
│  Registry, MCP Gateway, Model Gateway,      │
│  Memory Service, Checkpoint Service         │
│  Approval Service, Secret Manager           │
│                                             │
│  [PostgreSQL, Redis, Vector DB]             │
└─────────────────────────────────────────────┘
    │ (internal network, mTLS)
    ▼
┌─────────────────────────────────────────────┐
│           Zone 3: Execution                 │
│  Agent Workers, Tool Workers, Sandbox       │
│                                             │
│  ⚠ No direct internet access               │
│  ⚠ No database access                       │
│  ⚠ Ephemeral storage only                   │
│  ⚠ gVisor / Firecracker sandboxing          │
└─────────────────────────────────────────────┘
    │ (policy-controlled, audited)
    ▼
┌─────────────────────────────────────────────┐
│           Zone 4: External (Internet)       │
│  MCP Servers, LLM APIs, 3rd-party systems   │
│  (Access ONLY through MCP/Model Gateway)    │
└─────────────────────────────────────────────┘
```

### Zone Isolation Rules

| Traffic Path | Allowed? | Protocol | Notes |
|-------------|----------|----------|-------|
| Internet → API Gateway | ✅ | HTTPS | TLS 1.3 |
| API Gateway → Control Plane | ✅ | gRPC | mTLS |
| Control Plane → Execution | ✅ | gRPC | mTLS, least privilege |
| Worker → Internet | ❌ | — | Must go through MCP Gateway |
| Worker → Database | ❌ | — | Must go through owning service |
| MCP Gateway → External MCP | ✅ | HTTPS | Policy-controlled, audited |
| Model Gateway → LLM API | ✅ | HTTPS | Policy-controlled, audited |

## 2. Secrets Management

### Principle
No secrets stored in code, configuration files, or environment variables. All secrets retrieved at runtime from a centralized Secret Manager.

### Architecture

```
Secret Manager (HashiCorp Vault / Cloud KMS)
    │
    ├── Tenant Secrets (API keys, DB credentials)
    ├── MCP Server Secrets (auth tokens)
    ├── LLM Provider Secrets (API keys)
    └── Internal Secrets (service-to-service mTLS)
```

### Injection Pattern

1. Service requests secret by reference (e.g., `secret://vault/tenants/abc/salesforce-key`).
2. Secret Manager authenticates the requesting service (mTLS).
3. Secret is injected ephemerally (tmpfs, in-memory only).
4. Secret is never written to disk or logs.

### Secret Types

| Secret Type | Storage | Access Control |
|-------------|---------|---------------|
| Tenant API Keys | Vault KV | Service identity + RBAC |
| MCP Auth Tokens | Vault KV | Service identity + policy |
| LLM API Keys | Vault KV | Service identity + tier |
| DB Credentials | Vault Dynamic Secrets | Auto-rotated, per-service |
| mTLS Certs | Vault PKI | Auto-renewed |

## 3. Encryption

### Data at Rest

| Storage | Encryption | Key Management |
|---------|-----------|---------------|
| PostgreSQL | AES-256 | Cloud KMS / Vault Transit |
| Redis | AES-256 (AOF / RDB) | Cloud KMS |
| Vector DB | AES-256 | Cloud KMS |
| Object Storage (S3) | AES-256 (SSE) | Cloud KMS |
| Checkpoint Blobs | AES-256 | Tenant-specific key |

### Data in Transit

| Path | Encryption | Standard |
|------|-----------|----------|
| External (Internet) | TLS 1.3 | HTTPS |
| Internal (gRPC) | mTLS | TLS 1.3 |
| Internal (Event Bus) | TLS | Kafka/Redis TLS |
| Database connections | TLS | PostgreSQL TLS |

## 4. Access Control (IAM)

### Authentication

| Method | Use Case |
|--------|----------|
| JWT (Bearer token) | External API users |
| mTLS client certs | Internal service-to-service |
| API keys | MCP Server authentication |
| SSO (OIDC/OAuth2) | Enterprise users (Phase 6+) |

### Authorization (RBAC)

| Role | Scope | Permissions |
|------|-------|-------------|
| `admin` | Tenant | Full access to all resources |
| `developer` | Workspace | Create/edit Agents, view logs |
| `viewer` | Workspace | Read-only access |
| `operator` | Tenant | Manage executions, approve/reject |
| `compliance` | Tenant | View audit logs, policies (read-only) |

### Row-Level Security (PostgreSQL RLS)

All tenant-scoped tables enforce RLS:
```sql
CREATE POLICY tenant_isolation ON agents
  FOR ALL USING (tenant_id = current_setting('app.tenant_id')::UUID);
```

## 5. Audit

### What is Logged
- Every policy evaluation (ALLOW, DENY, REQUIRE_APPROVAL).
- Every tool execution request and result.
- Every Agent lifecycle change (start, stop, pause, resume).
- Every checkpoint creation and restore.
- Every secret access (metadata only, not secret value).

### Audit Log Structure

```json
{
  "id": "audit_001",
  "tenant_id": "tenant_abc",
  "timestamp": "2026-01-01T10:00:00Z",
  "actor": { "type": "agent", "id": "agent_123", "execution_id": "exec_456" },
  "action": "tool.execute",
  "resource": "mcp.github.read_repo",
  "decision": "ALLOWED",
  "policy_ref": "pol_789",
  "metadata": { "repo": "company/project", "access_level": "read" }
}
```

### Audit Log Immutability
- Audit logs are append-only.
- No DELETE or UPDATE operations permitted.
- Retention is configurable (minimum 1 year for compliance).
- Logs are stored in a separate database partition for isolation.

## 6. Compliance Mapping

| Standard | Requirement | Kitematic Implementation |
|----------|-------------|--------------------------|
| SOC2 | Access control | RBAC + mTLS + JWT |
| SOC2 | Audit | Immutable audit_logs |
| SOC2 | Encryption | AES-256 at rest, TLS 1.3 in transit |
| HIPAA | Data isolation | Dedicated tenant clusters |
| HIPAA | Access logs | Audit trail + approval tracking |
| ISO27001 | Change management | ADR + Change Control process |
| ISO27001 | Supplier security | Adapter Trust Levels + Security Scans |
