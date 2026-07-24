# Roadmap

## v1.0.x — Maintenance (current)

Critical bug fixes and security patches only.

- No new features
- Backport policy: security fixes to last 2 MINOR releases
- Branch: `v1.0.x` (create from `v1.0.0` tag)

## v1.1.0 — Platform Evolution (next)

Target: performance, developer experience, and platform expansion.

### Areas

| Area | Focus |
|---|---|
| Performance | Reduce P95 latency, optimize checkpoint throughput, reduce memory footprint |
| Developer Experience | SDK improvements, better error messages, local dev tooling |
| Platform Expansion | Additional MCP adapters, broader tool registry, more deployment targets |
| Observability | Enhanced dashboard panels, custom metric exporters, log aggregation improvements |

### Non-goals

- Distributed Runtime (leader election, cluster coordination) — deferred to v2.x
- Architectural redesigns — v1.x is API-stable

## v2.x — Distributed Runtime (future)

- Leader election for active/passive HA
- Distributed ownership of execution state
- Cluster coordination for multi-region deployments
- Horizontal scaling across data centers

---

See [VERSIONING_POLICY.md](VERSIONING_POLICY.md) for versioning rules and support timelines.
