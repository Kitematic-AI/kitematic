# P5 — Operations & Production Excellence

## Baseline (pre-P5)

| Metric | Value |
|--------|-------|
| Test count (runtime) | 644 passed, 2 skipped, 0 failures |
| Test count (project) | 899 passed, 3 failed, 2 skipped |
| Coverage (runtime) | 91% branch, 92% line |
| CI/CD | None |
| Container scanning | None |
| Dependency scanning | None |
| SBOM | None |
| OTel validation | Code only, never verified against collector |
| Dashboards | None |
| Alerting | None |
| SLO/SLI | Not defined |
| Backup/DR plan | None |
| Incident runbook | None |
| Chaos tests | 7 tests (mocked only, no infra) |

## Principles

1. **Exit criteria are measurable** — each step is complete ONLY when its criteria are met
2. **Progressive hardening** — CI gates first, then observability validation, then chaos
3. **Artifacts over activity** — dashboards, runbooks, backups, and **demonstrable recovery** are real deliverables
4. **No per-package coverage regression** — even if the average stays above threshold
5. **SLOs before dashboards** — define reliability targets before visualizing them

---

## P5.1 — CI/CD + Coverage + Quality Gates

**Goal**: No code change merges without automated verification.

### Quality Gates (merge must pass ALL)

| Gate | Tool | Target |
|------|------|--------|
| Tests | pytest | 0 failures |
| Coverage (runtime) | pytest-cov | >= 90% overall |
| Coverage per package | pytest-cov | No regression from baseline |
| Lint | ruff | 0 errors |
| Type checking | mypy | 0 errors |
| Dependency audit | pip-audit | 0 known vulns |
| Container build | docker build | Image builds |

Type checking is added because the codebase uses typing extensively (Protocols, dataclasses, `Any | None` unions). mypy catches interface violations that tests miss.

### No per-package regression

The CI computes coverage per package (e.g. `runtime/events/`, `runtime/api/`, `runtime/observability/`). If any package's coverage drops below its recorded baseline, CI fails — even if the average remains >= 90%.

### Deliverables

| File | Purpose |
|------|---------|
| `.github/workflows/ci.yml` | All quality gates on every PR + push |
| `.github/workflows/release.yml` | Build + publish Docker image on tag |
| `Makefile` | Local dev commands: `make test`, `make lint`, `make coverage` |

### CI Pipeline (`.github/workflows/ci.yml`)

```yaml
on: [pull_request, push]
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pip install -e ".[dev,redis,otel]"
      - run: ruff check runtime/ tests/
      - run: mypy runtime/ --strict  # or appropriate level
      - run: pip-audit --strict
      - run: pytest tests/ --tb=line --cov=runtime --cov-fail-under=90
      - run: docker build -t kitematic-api .
```

### Exit Criteria

| Criterion | Target | How to verify |
|-----------|--------|---------------|
| CI passes per PR | 100% | GitHub Actions status check |
| Coverage (runtime) | >= 90% | --cov-fail-under=90 gate |
| Coverage per package | No regression | Per-package comparison script |
| Ruff violations | 0 errors | ruff check exit code 0 |
| Mypy violations | 0 errors | mypy exit code 0 |
| pip-audit | 0 known vulns | pip-audit --strict exit 0 |
| Docker build | Image builds | docker build success |

---

## P5.2 — Security & Supply Chain

**Goal**: Zero critical/high vulnerabilities before any release.

### Tools

| Tool | Scope | Current | Install in CI |
|------|-------|---------|---------------|
| pip-audit | Python dependencies | Missing | pip install pip-audit |
| trivy | Container + filesystem | Missing | aquasecurity/trivy-action |
| cyclonedx-bom | SBOM generation | Missing | pip install cyclonedx-bom |
| bandit | Python AST security | Missing | pip install bandit |
| ruff | Lint | Available (0.15.20) | Already in dev deps |
| gitleaks | Secrets in repo | Missing | gitleaks-action |

### Scanning Schedule

- **Every PR (P5.1 CI)**: pip-audit --strict + bandit -r runtime/ + gitleaks
- **On release tag**: Trivy scan Docker image + generate SBOM
- **Weekly**: Full dependency audit + container rescan

### Deliverables

| File | Purpose |
|------|---------|
| `.github/workflows/security.yml` | Weekly scheduled security audit |
| `deploy/trivyignore` | Documented trivy exceptions (if any) |
| `docs/SECURITY.md` | Vulnerability disclosure policy + expected response times |

### Exit Criteria

| Criterion | Target | How to verify |
|-----------|--------|---------------|
| pip-audit per PR | 0 known vulns | CI gate (P5.1) |
| Bandit | 0 HIGH/CONFIDENCE | bandit -r runtime/ -ll exit 0 |
| Trivy (container) | 0 CRITICAL/HIGH | trivy image kitematic-api |
| SBOM | Generated per release | cyclonedx-py produces valid XML |
| Secrets in repo | 0 leaks | gitleaks scan exit 0 |
| Security policy | Published | docs/SECURITY.md exists |

---

## P5.3 — Observability Validation

**Goal**: Prove that traces, metrics, and logs actually reach their targets AND can be correlated.

This is the most critical step. P4.1 wired OTel into the codebase. P5.3 proves the pipeline end-to-end with a real collector.

### Three-Way Correlation

The key test: emit one execution, then verify that its **trace**, **metrics**, and **logs** all carry the same `execution_id` correlation key.

```
Execution started (execution_id: exec-123)
  │
  ├── OTel Span (trace_id: abc, execution_id: exec-123)
  ├── Metrics counter incremented (runtime.executions.total +1, labels: {execution_id: exec-123})
  └── JSON Log line (correlation: {execution_id: exec-123})
```

### Integration Tests

| Test | What it proves | Infrastructure needed |
|------|---------------|----------------------|
| `test_trace_reaches_collector` | Span with expected attributes received by OTLP collector | docker-compose.otel.yml |
| `test_metric_reaches_prometheus` | Counter value readable from Prometheus API | docker-compose.otel.yml |
| `test_log_has_correlation_id` | JSON log line contains execution_id, tenant_id, agent_id | Runtime (no infra) |
| `test_trace_metric_log_correlation` | All three carry same execution_id | docker-compose.otel.yml |
| `test_shutdown_flush` | No spans lost on graceful shutdown | docker-compose.otel.yml |
| `test_otel_disabled_fallback` | No crash when OTel is not configured | Runtime (no infra) |

### Deliverables

| File | Purpose |
|------|---------|
| `tests/integration/test_observability_e2e.py` | All integration tests above |
| `docker-compose.otel.yml` | Compose profile: API + Redis + OTel collector + Prometheus |
| `deploy/prometheus/prometheus.yml` | Scrape config for kitematic-api |
| `deploy/otel-collector.yml` | Collector config (already exists, may need update) |

### Exit Criteria

| Criterion | Target | How to verify |
|-----------|--------|---------------|
| Trace reaches collector | Span with execution_id attribute | integration test |
| Metric reaches Prometheus | Counter value matches expected | curl prometheus:9090/api/v1/query |
| Log has correlation | JSON line with execution_id + tenant_id | unit test (no infra) |
| Three-way correlation | Same execution_id in trace + metric + log | integration test |
| Graceful shutdown | 0 spans lost | integration test with flush |
| No-OTel mode | No crash, no error when collector absent | unit test |

---

## P5.4 — SLO/SLI + Alerting + Dashboards

**Order matters**: SLIs → SLOs → Alert Rules → Dashboards (not the reverse).

### Step 1: Define SLIs

| SLI | Source | Definition |
|-----|--------|------------|
| Availability | Health probe responses | `up / total` (sliding 5m window) |
| Execution latency | OTel trace duration | p50 / p95 / p99 of `execution.duration_ms` |
| Execution throughput | Metrics counter | `rate(runtime.executions.completed[5m])` |
| Error rate | Metrics counters | `runtime.executions.failed / runtime.executions.total` |
| Quota utilization | Metrics gauge | `concurrent / max_concurrent` per tenant (max across tenants) |

### Step 2: Set SLO Targets

| SLO | Target | Measurement window | Burn rate alert threshold |
|-----|--------|-------------------|--------------------------|
| API availability | >= 99.9% | 30 days | 99.8% over 1h (3x burn) |
| Execution latency p99 | <= 500ms | 7 days | 750ms over 10m |
| Error rate | <= 1% of executions | 7 days | 3% over 5m |
| Quota exhaustion | <= 0.1% of requests | 7 days | 0.5% over 5m |

Burn rate alerts fire when error budget is being consumed faster than the SLO allows, giving time to react before the SLO is breached.

### Step 3: Alert Rules (Prometheus)

| Alert | Condition | Severity | Response time |
|-------|-----------|----------|---------------|
| HighErrorRate | error_rate > 5% for 5m | critical | 5 min |
| HighLatency | p99 > 1s for 5m | warning | 15 min |
| QuotaExhaustion | quota_blocked > 1% of requests | warning | 15 min |
| ServiceDown | up == 0 for 1m | critical | immediate |
| BurnRate | error_rate > SLO burn rate for 1h | critical | 15 min |

### Step 4: Dashboards (Grafana)

Two dashboards, created AFTER SLOs are defined:

1. **Kitematic Overview**: All SLIs + SLO compliance + alert status
2. **Per-Tenant**: Quota utilization, execution rate, error rate by tenant

### Deliverables

| File | Purpose |
|------|---------|
| `docs/SLO.md` | SLI definitions + SLO targets + ownership + error budget policy |
| `deploy/prometheus/rules/alerts.yml` | Prometheus alerting rules |
| `deploy/grafana/dashboards/kitematic-overview.json` | Overview dashboard |
| `deploy/grafana/dashboards/kitematic-tenants.json` | Per-tenant dashboard |

### Exit Criteria

| Criterion | Target | How to verify |
|-----------|--------|---------------|
| SLO documented | Published in repo | docs/SLO.md exists with all 4 SLIs and targets |
| Alerts configured | 5 alert rules active | Prometheus rules API returns rules |
| Dashboard(s) exist | 2 dashboards in Grafana | Grafana API returns dashboard UIDs |
| Burn rate alert testable | Violation triggers alert | Test: inject error rate, verify alert fires |

---

## P5.5 — Backup & Disaster Recovery

**Goal**: Recover from total Redis data loss within documented RTO/RPO — **proven by a practical test**, not just a document.

### RTO / RPO Targets

| Component | RTO | RPO |
|-----------|-----|-----|
| Redis (event streams, rate limiter state) | <= 5 min | <= 1 min |
| Configuration (ConfigMap, env) | <= 2 min | N/A (immutable / git) |
| Application state | N/A | N/A (stateless — pod restart is sufficient) |

### Backup Strategy

- **Redis**: Scheduled BGSAVE every 5 minutes via cron or Kubernetes CronJob. Copy `dump.rdb` to object storage (S3/GCS).
- **Config**: Git is source of truth. `kubectl get configmap -o yaml` as verification only.
- **Secrets**: External secrets operator (AWS Secrets Manager / HashiCorp Vault). Never in Git.

### Practical Recovery Test

The DR drill proves the system can recover within RTO/RPO:

1. **Inject failure**: Delete Redis pod + data (`kubectl delete pod redis && kubectl exec redis -- rm /data/dump.rdb`)
2. **Measure**: Time starts when data is deleted
3. **Restore**: Execute `scripts/restore-redis.sh` — restore latest backup
4. **Verify**:
   - Health endpoint returns 200
   - Recent executions are replayable via Redis Streams
   - Rate limiter state restored (quota counters correct)
5. **Measure**: Time ends when all verifications pass

Automated as a scheduled GitHub Actions workflow (quarterly).

### Deliverables

| File | Purpose |
|------|---------|
| `docs/ops/disaster-recovery.md` | DR plan + step-by-step recovery + RTO/RPO definitions |
| `scripts/backup-redis.sh` | Redis RDB backup script |
| `scripts/restore-redis.sh` | Redis restore + verification script |
| `.github/workflows/dr-drill.yml` | Quarterly automated DR drill |

### Exit Criteria

| Criterion | Target | How to verify |
|-----------|--------|---------------|
| Backup script | Runs and produces valid RDB | ./scripts/backup-redis.sh && file dump.rdb |
| Restore script | Restores + verifies health | ./scripts/restore-redis.sh from backup |
| DR document | Published in repo | docs/ops/disaster-recovery.md exists |
| DR drill passes | Recovery within RTO | GA workflow succeeds (measured < 5 min) |
| DR drill automated | Scheduled quarterly | .github/workflows/dr-drill.yml exists |

---

## P5.6 — Incident Runbooks & Release/Rollback

### Runbooks

| Runbook | Covers |
|---------|--------|
| `docs/ops/runbooks/api-down.md` | Health probe failing, pod crash loop, high latency, 5xx spike |
| `docs/ops/runbooks/redis-failure.md` | Redis unreachable, replication lag, data loss, OOM |
| `docs/ops/runbooks/quota-exhaustion.md` | Distinguishing legitimate spike vs. attack vs. misconfiguration |
| `docs/ops/runbooks/capacity.md` | Pods stuck pending, OOMKilled, CPU throttle, HPA maxed |

Each runbook follows the same template:
- **Symptoms** (what you see in dashboards/alerts)
- **Severity** (critical / warning)
- **Immediate actions** (response within first 5 minutes)
- **Investigation** (logs, metrics, traces to check)
- **Resolution** (how to fix)
- **Verification** (how to confirm it's resolved)
- **Postmortem** (link to template)

### Release Process

```
1. PR merged -> CI passes (P5.1 gates) -> Docker image built + tagged
2. Deploy to staging -> integration tests pass (P5.3)
3. Security scan passes (P5.2)
4. Canary deploy (1 pod, 5% traffic) -> observe for 5 minutes
5. Rollout gradually (maxSurge: 1, maxUnavailable: 0)
6. Post-deploy verification: health + dashboards + SLO for 10 minutes
7. If metrics degrade -> kubectl rollout undo deployment/kitematic-api
8. Rollback verification: health + dashboards confirm recovery
```

### Deliverables

| File | Purpose |
|------|---------|
| `docs/ops/runbooks/api-down.md` | API failure runbook |
| `docs/ops/runbooks/redis-failure.md` | Redis failure runbook |
| `docs/ops/runbooks/quota-exhaustion.md` | Quota exhaustion runbook |
| `docs/ops/runbooks/capacity.md` | Capacity runbook |
| `docs/ops/release-process.md` | Release checklist with canary + rollback |
| `docs/ops/rollback.md` | Rollback procedure (separate for quick reference) |

### Exit Criteria

| Criterion | Target | How to verify |
|-----------|--------|---------------|
| Runbooks exist | 4 runbooks with all sections | docs/ops/runbooks/*.md |
| Release process documented | 1 page, executable step-by-step | docs/ops/release-process.md |
| Rollback documented | Separate quick-reference | docs/ops/rollback.md |
| Release drill completed | Canary + rollback tested manually | Sign-off in repo |

---

## P5.7 — Chaos & Resilience Validation

**Current**: 7 chaos tests exist in `tests/chaos/` but all use mocks. Need real infrastructure tests.

**Policy**: Chaos tests run nightly / on-demand (not per PR). CI must complete in under 15 minutes, but chaos tests require Kubernetes + real Redis and may take 5-10 minutes per scenario.

### Test Matrix

| Test | Failure injected | Expected behavior | Current status |
|------|-----------------|-------------------|----------------|
| Redis disconnect | Stop Redis pod | API returns 503, events queued locally, reconnection recovers | Mocked |
| Pod restart | kubectl delete pod | New pod serves, zero execution data loss | Missing |
| Network partition | Block Redis port 6379 | Degraded (no event persistence), no crash | Missing |
| Slow consumer | Delay in StreamConsumer loop | Backpressure, consumer lag alert fires | Missing |
| Certificate expiry | (Manual / simulated) | Graceful error, alert fires | Missing |

### Execution Schedule

| Schedule | Scope |
|----------|-------|
| **Nightly** (scheduled) | Full chaos test suite against staging cluster |
| **Pre-release** (manual trigger) | Full suite before cutting release tag |
| **On-demand** (workflow_dispatch) | Debug specific failure scenarios |

### Deliverables

| File | Purpose |
|------|---------|
| `tests/chaos/test_redis_disconnect.py` | Real Redis failover (requires k8s) |
| `tests/chaos/test_pod_restart.py` | Pod restart recovery |
| `.github/workflows/chaos-nightly.yml` | Nightly chaos drill |
| `docs/ops/chaos-engineering.md` | Chaos principles + test matrix + results log |

### Exit Criteria

| Criterion | Target | How to verify |
|-----------|--------|---------------|
| Redis failover test | Recovery within 30s | Nightly chaos workflow |
| Pod restart test | Zero execution data loss | Nightly chaos workflow |
| All chaos tests | >= 95% pass rate (30-day rolling) | Nightly workflow report |
| Graceful degradation | No crash, only error responses | Network partition test |
| Chaos schedule | Nightly + pre-release | .github/workflows/chaos-nightly.yml |

---

## Summary: P5 Final Exit Criteria

| Step | Key Metric | Target | Measured By |
|------|-----------|--------|-------------|
| **P5.1** | CI pass rate | 100% per PR | GitHub Actions (7 gates) |
| **P5.1** | Coverage (runtime) | >= 90% + no per-package regression | --cov-fail-under=90 + per-package comparison |
| **P5.2** | Vulnerabilities (dep + container) | 0 CRITICAL/HIGH | pip-audit + trivy |
| **P5.2** | Secrets in repo | 0 leaks | gitleaks |
| **P5.3** | OTel e2e correlation | Trace + Metric + Log share execution_id | Integration test with collector |
| **P5.4** | SLOs defined | All 4 SLOs + alert rules | docs/SLO.md + Prometheus rules |
| **P5.4** | Dashboards | 2 Grafana dashboards deployed | Grafana API |
| **P5.5** | DR drill | Recovery within RTO (<= 5 min) | Automated quarterly drill |
| **P5.6** | Runbooks | 4 published + release process | File existence + drill sign-off |
| **P5.7** | Chaos pass rate | >= 95% (30-day rolling) | Nightly workflow report |

---

## How to read this plan

Each P5.x section lists:
- **Goal** — what we achieve
- **Exit Criteria** — how we know it's done (measurable, automatable, or demonstrable)
- **Deliverables** — files to create or modify (artifacts, not activity)
- **Current baseline** — so we know the gap

P5 is complete when ALL exit criteria across ALL steps are met.

P4.6 (Distributed Runtime) begins only after P5 exit criteria are verified.
