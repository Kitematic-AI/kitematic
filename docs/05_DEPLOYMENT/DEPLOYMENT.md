# Deployment Architecture (Version 1.0)

## Deployment Topologies

Kitematic supports four tiers of deployment isolation:

| Tier | Mode | Suitable For | Isolation |
|------|------|-------------|-----------|
| 1 | Shared SaaS | Free, Developer | Kubernetes Namespace + Resource Quotas |
| 2 | Dedicated SaaS | Teams, Pro Business | Dedicated Namespace + RBAC + Network Policies |
| 3 | Enterprise | Regulated Industries | vCluster / Dedicated Cluster + Dedicated DB |
| 4 | Air-Gapped | Government, Defense, Banking | Private K8s + Firecracker + Offline |

## Kubernetes Namespace Strategy

- `kitematic-system` — Control Plane services (Orchestrator, Policy Engine)
- `kitematic-data` — Databases (PostgreSQL, Redis, Vector DB) — network isolated
- `tenant-{id}-execution` — Per-tenant sandbox pools — ephemeral

## Zero-Trust Network Policies

- **Default Deny All** — No pod-to-pod communication without explicit policy.
- **Worker Egress Blocked** — Agent Workers cannot reach the internet. Only MCP Gateway can make external calls.
- **Data Tier Isolation** — Execution plane cannot connect to databases directly. All access via gRPC through Control Plane.

## Secrets Management

- HashiCorp Vault or Cloud KMS.
- Secrets injected as memory-only volumes (tmpfs) at runtime.
- Never stored in environment variables or config files.

## GPU Scheduling

- GPU Node Pools with MIG support for multi-tenant GPU sharing.
- Model Gateway monitors VRAM and routes requests.
- Auto-fallback to cloud models when local GPU unavailable (policy permitting).

## Air-Gapped Installation

- Distributed as a bundled tarball (Helm Charts + Docker Images + Model Weights).
- `offline_mode: true` disables all external telemetry and update checks.
- Local model registry and private adapter hub included.

## Backup & Disaster Recovery

- PostgreSQL WAL Archiving for continuous backup.
- Velero for Kubernetes cluster state backup.
- Checkpoints stored in object storage (S3-compatible) for cross-region DR.

## Enterprise Compliance Mapping

| Standard | Kitematic Feature |
|----------|-------------------|
| SOC2 | Immutable audit_logs, Policy Engine, Access Controls |
| HIPAA | Dedicated isolation mode, Encryption at rest, Access audit |
| ISO27001 | RBAC, Secrets management, Change control process |
