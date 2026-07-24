# P5.6 — Incident Response & Operational Runbooks

## Table of Contents

1. [Incident Classification](#1-incident-classification)
2. [Incident Lifecycle](#2-incident-lifecycle)
3. [On-call Playbooks](#3-on-call-playbooks)
4. [Escalation Matrix](#4-escalation-matrix)
5. [Postmortem Template](#5-postmortem-template)
6. [Operational Checklists](#6-operational-checklists)
7. [Game Days](#7-game-days)

---

## 1. Incident Classification

### Severity Matrix

| Severity | Definition | Examples | Response Time | SLA Impact |
|---|---|---|---|---|
| **P0** | Complete service outage or data loss | API returns 5xx for all requests; Redis cluster destroyed; checkpoint data loss | 15 min pager | SLO violation imminent |
| **P1** | Major feature degradation for most users | P95 latency > 1s; Gateway failure rate > 10%; rate limiting all tenants | 30 min pager | SLOs burning |
| **P2** | Partial degradation or single-tenant issue | One MCP server down; policy evaluation errors for one tenant | 4 hours ticket | Minor SLO impact |
| **P3** | Cosmetic or non-urgent | Dashboard stale; log format issue; non-critical alert | Next business day | No SLO impact |

### Severity Transition Rules

| Transition | Condition | Owner |
|---|---|---|
| P3 → P2 | Issue affects > 1 tenant or lasts > 24h | On-call engineer |
| P2 → P1 | Error rate exceeds 50% of SLO threshold | Incident commander |
| P1 → P0 | Service is fully unavailable | Incident commander + engineering lead |
| Any → Closed | Verified recovery + 30 min stable | On-call engineer |

### Communication by Severity

| Severity | Channel | Updates | Participants |
|---|---|---|---|
| P0 | Pager + Slack + Email | Every 30 min | All engineering + management |
| P1 | Pager + Slack | Every 60 min | Platform team + on-call |
| P2 | Slack | Every 24h | Affected team |
| P3 | Jira ticket | Upon close | Reporter |

---

## 2. Incident Lifecycle

```
          ┌─────────┐
          │ DETECT  │  ← Alert, user report, monitoring dashboard
          └────┬────┘
               ▼
          ┌─────────┐
          │ TRIAGE  │  ← Classify severity, assess impact, declare
          └────┬────┘
               ▼
       ┌──────────────┐
       │ ASSIGN OWNER │  ← Incident commander named
       └──────┬───────┘
              ▼
       ┌───────────┐
       │ MITIGATE  │  ← Stop the bleeding (rollback, scale, failover)
       └─────┬─────┘
             ▼
       ┌───────────┐
       │ RECOVER   │  ← Restore to normal operation
       └─────┬─────┘
             ▼
       ┌───────────┐
       │ VERIFY    │  ← Confirm recovery + 30 min stable period
       └─────┬─────┘
             ▼
       ┌───────────┐
       │ CLOSE     │  ← Declare incident resolved
       └─────┬─────┘
             ▼
       ┌────────────┐
       │ POSTMORTEM │  ← Required for P0/P1, optional for P2
       └────────────┘
```

### Lifecycle Phase Details

| Phase | Duration (target) | Artifacts |
|---|---|---|
| Detect | < 1 min | Alert notification or user report |
| Triage | < 5 min | Severity classification, initial Slack message |
| Assign Owner | < 2 min | Named in incident Slack channel |
| Mitigate | < RTO | Rollback, failover, scale-out action |
| Recover | < RTO | Service restored to healthy state |
| Verify | 30 min | Monitoring confirms stability |
| Close | < 5 min | Incident report summary |
| Postmortem | < 5 business days | Root cause, corrective actions |

---

## 3. On-call Playbooks

### 3.1 API Down

**Detection**:
- Alert: `APIHighErrorRate` or `API Availability < 99.9%`
- Symptom: HTTP 503/502 for all requests

**Immediate Actions**:
1. Check K8s pod status: `kubectl get pods -l app=kitematic`
2. Check pod logs for crash: `kubectl logs --tail=50 -l app=kitematic`
3. Verify K8s service endpoints: `kubectl get endpoints kitematic-api-service`

**Rollback**:
```
kubectl rollout undo deployment/kitematic-api
kubectl rollout status deployment/kitematic-api
```

**Verification**:
```
curl -f http://localhost:8000/api/v1/health
# Expected: {"status": "ok"}
```

**Escalation**:
- First response: On-call engineer (15 min)
- Escalation: Platform team lead (30 min)
- P0 declaration: Engineering director

**Recovery Criteria**:
- API responds to health check
- Error rate < 0.1% for 5 minutes

---

### 3.2 Runtime Failure

**Detection**:
- Alert: `RuntimeHighFailureRate`
- Symptom: `runtime.executions.failed / runtime.executions.total > 0.005`

**Immediate Actions**:
1. Check failure breakdown in Operations Dashboard
2. Inspect recent execution logs for `error` field
3. Identify failing phase via Debug Dashboard traces

**Rollback**: N/A (runtime is stateless — restart clears transient state)

**Verification**:
```python
# Execute a test intent
import asyncio
from runtime.kitematic_runtime.runtime import Intent, KitematicRuntime
# ... verify success
```

**Escalation**: Platform team lead if failure rate > 50% for 10 min

**Recovery Criteria**:
- Failure rate < 0.5% for 10 minutes
- No `RuntimeError` in execution logs

---

### 3.3 Redis Failure

**Detection**:
- Alert: `RedisPublishErrors` or `ConsumerLagHigh`
- Symptom: Redis connection errors in logs

**Immediate Actions**:
1. Check Redis connectivity: `redis-cli -u redis://redis-service:6379 ping`
2. Fall back to `event_backend=memory`:
   ```
   kubectl patch configmap kitematic-config -p '{"data":{"KITEMATIC_EVENT_BACKEND":"memory"}}'
   kubectl rollout restart deployment kitematic-api
   ```
3. Restore Redis from AOF/RDB backup if data loss

**Verification**:
- `redis-cli ping` returns `PONG`
- Runtime logs show "Connected to Redis"

**Escalation**: Infrastructure team if Redis volume corrupted

**Recovery Criteria**:
- Redis responding to commands
- Event stream resuming (events published via `XADD`)
- Switch back to `redis_streams` backend after recovery

---

### 3.4 High Latency

**Detection**:
- Alert: `HighP95Latency`
- Symptom: P95 execution latency > 500ms for 10 min

**Immediate Actions**:
1. Open Debug Dashboard — check trace waterfall
2. Identify slow phase:
   - Gateway slow → check `gateway.tool.duration_ms` histogram
   - Checkpoint slow → check persistence backend
   - Internal slow → check CPU/memory
3. If Gateway: identify slow MCP server from debug panel
4. If MCP server slow: set client timeout or failover to another server

**Verification**:
- P95 latency returns below 500ms
- No slow traces in Debug Dashboard

**Escalation**: Platform team if latency > 1s for 30 min

**Recovery Criteria**:
- P95 latency < 500ms for 10 minutes
- No phase consistently > 200ms

---

### 3.5 Elevated Error Rate

**Detection**:
- Alert: Error rate > 2x baseline for any SLO
- Symptom: Spikes in `runtime.executions.failed`, `gateway.tool.mcp_failure`, etc.

**Immediate Actions**:
1. Determine the error category:
   - Policy rejections → check policy rules
   - Gateway failures → check MCP servers
   - Checkpoint errors → check persistence
   - Internal exceptions → check runtime logs
2. If deployment-related: rollback immediately
3. If dependency-related: failover to secondary

**Verification**:
```
# Check error rate
runtime.executions.failed / runtime.executions.total < 0.001
```

**Escalation**: Based on error category — see specific playbooks

**Recovery Criteria**:
- Error rate within normal range for 15 minutes
- No repeated errors in logs

---

### 3.6 Authentication Failure

**Detection**:
- Alert: `security.auth.failed` rate spike
- Symptom: Users reporting 401 errors

**Immediate Actions**:
1. Check API key fingerprint store in `api/auth.py`
2. Verify key rotation status
3. Check for expired keys or configuration drift
4. If key store corrupted: restore from backup or regenerate keys

**Verification**:
```bash
curl -H "X-API-Key: <test-key>" http://localhost:8000/api/v1/health
# Expected: 200
```

**Escalation**: Security team lead

**Recovery Criteria**:
- Auth success rate > 99.9%
- No 401 errors from valid keys

---

### 3.7 OTel Pipeline Failure

**Detection**:
- Alert: `CollectorUnavailable`
- Symptom: No new trace data in backend

**Immediate Actions**:
1. Check Collector process: `kubectl get pods -l app=otel-collector`
2. Check Collector logs: `kubectl logs -l app=otel-collector`
3. Verify OTLP endpoint: `curl -v telnet://otel-collector-service:4317`
4. If config error: fix and restart
5. If process crash: `kubectl rollout restart deployment otel-collector`

**Verification**:
- Collector starts and accepts connections
- Test span reaches backend (via Debug Dashboard)

**Escalation**: Observability team

**Recovery Criteria**:
- Collector healthy for 10 minutes
- Traces appearing in backend
- No gaps > 5 minutes in trace data

---

## 4. Escalation Matrix

### Tier 1: First Responder

| Role | Person | Coverage | Response Time |
|---|---|---|---|
| On-call engineer | Rotating weekly | 24/7 pager | 15 min (P0), 30 min (P1) |

### Tier 2: Technical Lead

| Role | Person | Trigger | Response Time |
|---|---|---|---|
| Platform lead | Senior engineer | P1 unresolved after 30 min, any P0 | 15 min during business hours |
| Infrastructure lead | DevOps engineer | Redis, K8s, networking issues | 30 min |

### Tier 3: Management

| Role | Person | Trigger | Response Time |
|---|---|---|---|
| Engineering director | EM | P0 unresolved after 1 hour, cross-team coordination | Immediate |
| VP Engineering | VP Eng | P0 > 2 hours, customer escalation | Immediate |

### Escalation Flow

```
On-call Engineer (T1)
    │ 15 min no response / cannot resolve
    ▼
Platform Lead (T2)
    │ 30 min no progress / P0 declared
    ▼
Engineering Director (T3)
    │ 2 hours unresolved / customer impact
    ▼
VP Engineering (Executive)
```

### P0 Declaration Authority

| Role | Can Declare P0 | Can Close P0 |
|---|---|---|
| On-call engineer | Yes | Yes (after verification) |
| Platform lead | Yes | Yes |
| Engineering director | Yes | Yes |
| VP Engineering | Yes | Yes |

---

## 5. Postmortem Template

```markdown
# Postmortem: <incident-title>

**Date**: YYYY-MM-DD
**Severity**: P0 / P1
**Duration**: <start> → <end> (X hours Y minutes)
**Impact**: X failed requests, Y affected tenants, Z% error rate

## Timeline

| Time (UTC) | Event |
|---|---|
| HH:MM | Detection — <how> |
| HH:MM | Triage — <severity, initial assessment> |
| HH:MM | Mitigation — <action taken> |
| HH:MM | Recovery — <service restored> |
| HH:MM | Verification — <30 min stable> |
| HH:MM | Closure — <incident declared resolved> |

## Root Cause

<one paragraph describing why the incident happened>

## Contributing Factors

- <factor 1>
- <factor 2>

## Trigger

<what specifically caused the incident to start>

## Detection Gaps

- <was detection automatic? how long did it take to detect?>
- <would the alert have fired faster? what was missing?>

## Corrective Actions (completed during incident)

| Action | Owner | Status |
|---|---|---|
| <action> | <owner> | Done |

## Preventive Actions

| Action | Owner | Due Date |
|---|---|---|
| <action> | <owner> | YYYY-MM-DD |
| <action> | <owner> | YYYY-MM-DD |

## Action Items

- [ ] Track preventive actions in Jira
- [ ] Update runbook with lessons learned
- [ ] Schedule postmortem review

## Lessons Learned

- <what went well>
- <what went wrong>
- <what could be improved>
```

---

## 6. Operational Checklists

### 6.1 Pre-Deployment Checklist

```
[ ] All CI quality gates pass:
    [ ] ruff lint — 0 violations
    [ ] mypy strict — 0 errors
    [ ] pytest — all tests pass
    [ ] Coverage ≥ 90%
    [ ] pip-audit — 0 vulnerabilities
    [ ] bandit — 0 HIGH findings
[ ] Docker build passes: docker build -t kitematic-api .
[ ] Changelog updated
[ ] Version bumped in pyproject.toml
[ ] Deployment plan reviewed by peer
[ ] Rollback plan documented
[ ] Monitoring dashboards reviewed for new metrics
```

### 6.2 Post-Deployment Checklist

```
[ ] Health check passes: curl /api/v1/health
[ ] Error rate within baseline (first 5 min)
[ ] P95 latency within SLO (first 10 min)
[ ] All pods healthy: kubectl get pods
[ ] No crash loops
[ ] Logs show no unexpected errors
[ ] Alert: new version deployed in Slack #deployments
[ ] Canary: if gradual rollout, monitor for 15 min before full rollout
```

### 6.3 Rollback Checklist

```
[ ] Declare rollback in Slack #incidents
[ ] kubectl rollout undo deployment/kitematic-api
[ ] Wait for rollout status: kubectl rollout status deployment/kitematic-api
[ ] Verify health: curl /api/v1/health
[ ] Verify error rate returns to baseline
[ ] Monitor for 15 min before declaring stable
[ ] File bug for root cause
```

### 6.4 Scale-Out Checklist

```
[ ] Verify current load: CPU, memory, active executions
[ ] Check HPA status: kubectl get hpa
[ ] If manual scale: kubectl scale deployment kitematic-api --replicas=N
[ ] Verify new pods join: kubectl get pods -l app=kitematic
[ ] Verify load distribution: check per-pod metrics
[ ] Update HPA minReplicas if permanent change
```

### 6.5 DR Drill Checklist

```
[ ] Schedule drill: date, time, participants
[ ] Declare drill start in Slack #drills
[ ] Execute DR scenario (see P5.5 scenarios)
[ ] Measure RTO / RPO achieved
[ ] Document deviations from expected RTO/RPO
[ ] Declare drill complete
[ ] File follow-up items for gaps found
[ ] Update DR plan with lessons learned
```

---

## 7. Game Days

### Schedule

| Frequency | Exercise | Owner | Participants |
|---|---|---|---|
| **Monthly** | Incident Response Drill | On-call engineer | Platform team |
| **Quarterly** | DR Drill | Platform lead | Platform + Infrastructure |
| **Semi-annual** | Chaos Exercise | Engineering director | All engineering |

### Monthly Incident Drill

Simulate a production incident in staging environment:

1. Pick a scenario from the incident catalog
2. Trigger the scenario (simulate failure)
3. Follow the on-call playbook
4. Measure: time to detect, time to mitigate, time to recover
5. Document gaps

**Scenarios (rotate monthly)**:
- Month 1: API Down
- Month 2: Redis Failure
- Month 3: High Latency
- Month 4: Auth Failure
- Month 5: Runtime Failure
- Month 6: OTel Pipeline Failure

### Quarterly DR Drill

Execute a full DR scenario from P5.5:

1. Choose scenario: checkpoint corruption, runtime restart, or Redis loss
2. Execute recovery procedure from DR runbook
3. Measure RTO/RPO achieved
4. Update runbook with improvements

### Semi-annual Chaos Exercise

Run chaos experiments (see P5.7):
- Network latency injection
- Pod termination
- Resource exhaustion
- Dependency failure

### Drill Metrics

| Metric | Target |
|---|---|
| Time to detect | < 2 min |
| Time to triage | < 5 min |
| Time to mitigate (P0) | < RTO |
| Time to recover (P0) | < RTO |
| Runbook adherence | ≥ 90% of steps followed |

### Drill Reporting

After each drill, file a brief report:
```
Drill: <type>
Date: YYYY-MM-DD
Scenario: <name>
Detect: X min
Mitigate: X min
Recover: X min
Gaps: <list>
Follow-ups: <Jira issue links>
```
