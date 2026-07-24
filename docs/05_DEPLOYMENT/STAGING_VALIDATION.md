# RC-4: Staging Validation

## Overview

Before declaring a release candidate ready for sign-off, the system must run in a staging environment for a minimum of **24 continuous hours** meeting all exit criteria below.

## Prerequisites

- [ ] Staging cluster provisioned (or Docker Compose for local staging)
- [ ] RC image built and deployed: `kitematic-api:1.0.0-rc.X`
- [ ] Redis instance available (optional — memory backend for fallback testing)
- [ ] Monitoring dashboards accessible
- [ ] Alert rules configured and firing correctly
- [ ] All RC-1 through RC-3 gates passed

## Validation Period

**Duration**: 24 hours minimum (72 hours recommended for full confidence)
**Environment**: staging (isolated, not production)

## Exit Criteria

### 1. Runtime Stability

| Criterion | Measure | Pass/Fail |
|---|---|---|
| No crashes | Zero unexpected process terminations | |
| No restart loops | Pod restarts = 0 (excluding intentional) | |
| No memory leaks | RSS stable over 24h (±10% of initial) | |
| No goroutine/thread leak | Thread count stable over 24h (±5%) | |
| No file descriptor leak | FD count stable over 24h | |

### 2. SLO Compliance

| SLO | Target | Actual (24h) | Pass/Fail |
|---|---|---|---|
| API availability | ≥ 99.9% | | |
| Execution success rate | ≥ 99.5% | | |
| P95 latency | ≤ 500ms | | |
| Policy evaluation time | ≤ 50ms | | |
| Gateway response time | ≤ 2s | | |
| Checkpoint save time | ≤ 100ms | | |
| Event publish success | ≥ 99.9% | | |

### 3. Alerting

- [ ] All 14 alert rules fire correctly when conditions are triggered
- [ ] No false positives during validation period
- [ ] No alert storms (more than 5 alerts in 5 minutes unrelated to actual issues)
- [ ] All pager notifications reach the on-call contact

### 4. Dashboards

- [ ] Executive Dashboard — all panels populate
- [ ] Operations Dashboard — all panels populate
- [ ] Debug Dashboard — trace drill-down works
- [ ] All metric queries return within 5 seconds
- [ ] Dashboard refresh works at 1-minute interval

### 5. Trace/Log/Metric Correlation

- [ ] `trace_id` is present in logs for every execution
- [ ] `trace_id` links log entries to trace spans
- [ ] `trace_id` links metrics to execution context
- [ ] Failed executions produce error spans with correct attributes

### 6. Deployment Operations

- [ ] Health check responds 200: `curl /api/v1/health`
- [ ] Intent execution via REST API works
- [ ] Rolling update: zero-downtime deployment verified
- [ ] Rollback: `kubectl rollout undo` completes without data loss
- [ ] Scale-out: adding replicas distributes load evenly
- [ ] Config update: patching ConfigMap propagates correctly

### 7. Recovery Operations

- [ ] Redis disconnect → memory backend fallback works
- [ ] Redis reconnect → stream replay resumes
- [ ] Runtime restart preserves checkpoints
- [ ] Checkpoint corruption → backup recovery works

### 8. No Alert Storm

- [ ] Alert volume < 10 distinct alerts over 24h
- [ ] No repeating alerts for the same condition
- [ ] No noisy alerts that require tuning

## Validation Log

| Timestamp (UTC) | Check | Result | Notes |
|---|---|---|---|
| | | | |
| | | | |
| | | | |

## Sign-off

| Role | Name | Date | Signature |
|---|---|---|---|
| Validator | | | |
