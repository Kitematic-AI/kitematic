# Release Notes — Kitematic Runtime v1.0.0

**Release Date**: 2026-07-24
**Version**: 1.0.0 (Release Candidate)

## Overview

Kitematic Runtime v1.0.0 is the first stable release of the AI Operating System execution layer. It provides a production-grade runtime for AI agent execution with policy enforcement, multi-tenant isolation, OpenTelemetry observability, and comprehensive operations tooling.

## What's New

### Architecture & Runtime
- ABI-driven runtime with `KitematicRuntime`, `Intent`, and `ExecutionResult` contracts
- Policy evaluation engine with capability-based access control
- Multi-tenant isolation with per-tenant quotas
- State machine with validated transitions

### Security
- API key authentication with SHA-256 fingerprinting
- Constant-time comparison via `hmac.compare_digest`
- Security audit logging for all auth events
- Key rotation with metrics tracking

### Observability
- OpenTelemetry traces, metrics, and logs with OTLP export
- Trace/log/metric correlation via shared `trace_id`
- 13 SLIs, 7 SLOs with error budget policy
- 14 alert rules across 3 tiers

### Operations
- 6 disaster recovery scenarios with documented RTO/RPO
- 18 DR tests covering checkpoint corruption, runtime restart, Redis replay
- 8 operational runbooks
- Incident response framework (P0-P3)
- 27 chaos experiments across 7 categories
- Nightly/weekly/pre-release chaos CI

### Quality
- 647+ passing tests, 92%+ code coverage
- Zero HIGH/CRITICAL security findings
- Dependency freeze for reproducible builds
- 7-gate release validation workflow

## Upgrade Notes

This is the first stable release — no upgrade path from earlier 0.x versions is provided.

## Known Issues

- Redis stream replay tests require a running Redis instance (skipped in CI)
- Performance benchmarks require warm-up period for accurate results
- WebSocket endpoint uses deprecated query-param auth (migration to header-only in next release)

## Breaking Changes

- N/A — first stable release

## Deprecations

- WebSocket `api_key` query param auth: use `Authorization: Bearer <key>` header instead

## Release Artifacts

- **Image**: `ghcr.io/kitematic/kitematic-api:v1.0.0`
- **SBOM**: Available in GitHub Release artifacts
- **Checksums**: SHA-256 checksums in GitHub Release

---

For detailed documentation, see the [docs/](docs/) directory.
