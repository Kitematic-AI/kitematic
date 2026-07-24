# Changelog

All notable changes to Kitematic Runtime are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0-rc.1] — 2026-07-24

### Added

#### Architecture & Runtime (P1-P2)
- ABI-driven runtime architecture with `KitematicRuntime`, `Intent`, `ExecutionResult`, `ExecutionPath`
- Policy evaluation engine with `PolicyEvaluator` ABC, capability check, and isolation boundaries
- Multi-tenant isolation via `TenantContext`, `IsolationBoundary`, and per-tenant quota management
- State machine (`ExecutionState`, `RuntimeState`) with validated transitions
- Configuration system via `pydantic-settings` (`RuntimeSettings`)

#### Integration & Scaling (P3-P4)
- FastAPI web application with health check, intent execution, and WebSocket endpoints
- API key authentication with SHA-256 fingerprinting and constant-time comparison
- Audit logging for security-relevant events (auth success/failure, key rotation)
- Checkpoint system with `CheckpointPersistenceAdapter`, `FileSystemCheckpointRepository`, and atomic writes
- In-memory and file-system checkpoint backends with integrity hashing
- Tool registry and capability-based access control
- Quota management with `QuotaManager` and `TenantQuotaConfig`
- Concurrent execution support with proper thread safety

#### Production Hardening (P5)
- CI quality gates: ruff lint, mypy strict, pytest, coverage ≥ 90%, pip-audit, bandit
- Dependency vulnerability scanning via `pip-audit` and `trivy`
- AST-based security scanning via `bandit` with project-specific rules
- OpenTelemetry instrumentation: traces, metrics, and logs (OTLP exporter)
- OpenTelemetry E2E validation pipeline with trace/log/metric correlation
- SLO framework: 13 SLIs, 7 SLOs with error budget policy and burn rates
- 14 alert rules across 3 severity tiers (critical pager, warning ticket, info slack)
- 3 dashboard layouts: Executive, Operations, Debug
- 6 disaster recovery scenarios with RTO/RPO per service
- DR test suite: 18 tests (checkpoint corruption, runtime restart, Redis replay)
- Runbook library: 8 runbooks (API failure, runtime failure, gateway failure, latency, Redis, auth, error rate, OTel)
- Incident response framework: P0-P3 classification, lifecycle, escalation matrix
- Postmortem template with timeline, root cause, corrective/preventive actions
- Chaos engineering: 27 experiments across 7 categories (Runtime, Redis, Network, Storage, OTel, API, K8s)
- Chaos CI: nightly (light), weekly (medium), pre-release (full) with artifact collection
- Chaos guardrails: production protection, timeouts, teardown, RTO/RPO validation
- Release chaos gate: blocks release if critical experiments fail

### Changed
- Version bumped from 0.2.0 → 1.0.0-rc.1 (RC cycle)
- Upgraded from preliminary to production-grade auth with SHA-256 fingerprinting
- Unified `IntentionEngine` → `KitematicRuntime` with ABI contracts

### Fixed
- Checkpoint atomic write safety: tmp + replace pattern prevents partial writes
- Concurrent checkpoint races resolved via isolated file paths
- Auth provider: constant-time comparison via `hmac.compare_digest`
- Various security findings addressed (bandit baseline, dependency updates)

### Security
- API keys stored as SHA-256 fingerprints (never raw) in `APIKeyAuthProvider`
- Constant-time fingerprint comparison prevents timing attacks
- Key rotation support with metrics tracking
- Audit log for all auth events (success, failure, rotation)
- `.bandit.yaml` with project-specific security policies
- Dependency freeze ensures reproducible vulnerability-free builds

---

## [0.2.0] — 2026-07-XX

### Added
- Initial `KitematicRuntime` implementation with intent execution lifecycle
- Basic policy evaluation and tool gateway interfaces
- FastAPI web application with health check endpoint
- OpenTelemetry tracing and metrics integration
- Checkpoint system with file-system persistence
- Preliminary CI pipeline with ruff and pytest

---

## [0.1.0] — 2026-06-XX

### Added
- Project scaffolding and domain models
- Service boundary definitions
- Architecture decision records (ADR)
