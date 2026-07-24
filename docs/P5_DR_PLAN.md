# P5.5 — Disaster Recovery Plan

## Table of Contents

1. [DR Scenarios](#1-dr-scenarios)
2. [Recovery Objectives](#2-recovery-objectives)
3. [Recovery Procedures](#3-recovery-procedures)
4. [DR Test Suite](#4-dr-test-suite)
5. [Review Cadence](#5-review-cadence)

---

## 1. DR Scenarios

### Scenario Matrix

| # | Scenario | Category | RTO | RPO | Testable? | Last Test |
|---|---|---|---|---|---|---|
| DR-01 | Redis cluster total loss | Data | 15 min | 5 min | Partial | — |
| DR-02 | Checkpoint data corruption | Data | 30 min | 0 (zero) | Yes | — |
| DR-03 | Runtime pod crash | Compute | 2 min | 0 (zero) | Yes | — |
| DR-04 | OTel Collector outage | Observability | 30 min | 30 min | Yes | — |
| DR-05 | Failed deployment rollback | Deployment | 5 min | 0 (zero) | Yes | — |
| DR-06 | Full site loss (region failover) | Infrastructure | 4 hrs | 1 hr | No | — |

### Detailed Scenarios

#### DR-01: Redis Cluster Total Loss

**Trigger**: Redis cluster unreachable — all `XADD` / `PUBLISH` calls fail with connection errors.

**Impact**:
- New ExecutionEvents are NOT published (event streams lost).
- Existing subscribers receive NO events.
- Running executions CONTINUE (events are not on the critical path).
- Rate limiting degrades (QuotaManager depends on in-memory state, not Redis).

**RTO**: 15 minutes — time to restore Redis from AOF/RDB backup.
**RPO**: 5 minutes — events in the last 5 minutes before failure are lost.
**Mitigation**: `event_backend=memory` fallback via ConfigMap update (instant, zero RPO for new executions).

#### DR-02: Checkpoint Data Corruption

**Trigger**: JSON decode errors reading checkpoint files — file system corruption or manual tampering.

**Impact**:
- `CheckpointPersistenceError` during `restore()`.
- Execution state CANNOT be recovered.
- Running executions continue but cannot resume from last checkpoint.

**RTO**: 30 minutes — time to restore from backup or rebuild from execution replay.
**RPO**: Zero — previous successful checkpoint is always recoverable (atomic writes).
**Mitigation**: SHA-256 content hashing detects corruption. Atomic writes prevent partial writes.

#### DR-03: Runtime Pod Crash

**Trigger**: Pod crash (OOM, segfault, liveness probe failure).

**Impact**:
- In-flight executions are lost (no durability within a single execution step).
- K8s Deployment controller restarts the pod within 30s (default).
- HPA ensures 2+ replicas are running; another replica picks up new requests.

**RTO**: 2 minutes — time for K8s to restart pod + readiness probe to pass.
**RPO**: Zero — checkpoints are persisted in the checkpoint repository (file system or database), not in the pod.
**Mitigation**: Stateless runtime design — all durable state is in the checkpoint repository, not in the pod.

#### DR-04: OTel Collector Outage

**Trigger**: Collector process crash, OTLP endpoint unreachable.

**Impact**:
- OTel spans, metrics, and logs are dropped by the SDK's `BatchSpanProcessor`.
- Runtime CONTINUES to function — OTel is on the non-critical path.
- No data loss if collector returns within `OTEL_BSP_MAX_EXPORT_TIMEOUT` (default 30s).
- Continuous data loss if collector stays down (SDK buffer fills, then drops).

**RTO**: 30 minutes — time to restart Collector and verify pipeline.
**RPO**: Up to 30 minutes (SDK buffer timeout) — spans/metrics in memory may be lost.
**Mitigation**: Non-critical path — runtime unaffected. Verified in P5.3 export failure tests.

#### DR-05: Failed Deployment Rollback

**Trigger**: New deployment causes error rate spike — caught by CI quality gates or monitoring alerts.

**Impact**:
- Users receive errors or degraded performance.
- Automated rollback via K8s Deployment revision.

**RTO**: 5 minutes — `kubectl rollout undo deployment/kitematic-api`.
**RPO**: Zero — deployment changes no data.
**Mitigation**: CI quality gates (P5.1) + canary analysis via Gateway error rate alert.

#### DR-06: Full Site Loss

**Trigger**: Entire region/availability zone failure.

**Impact**: Complete service outage.

**RTO**: 4 hours — time to spin up new cluster in secondary region.
**RPO**: 1 hour — checkpoint data replicated with 1-hour frequency.
**Mitigation**: Multi-region K8s clusters (requires infrastructure investment — out of scope for P5.5).

---

## 2. Recovery Objectives

### Service-Level RTO/RPO

| Service | RTO | RPO | Dependencies |
|---|---|---|---|
| API Layer | 2 min | 0 | None (stateless) |
| Runtime Engine | 2 min | 0 | Checkpoint Repository |
| Gateway | 2 min | 0 | MCP Servers (external) |
| Redis Streams | 15 min | 5 min | Redis Cluster |
| OTel Pipeline | 30 min | 30 min | OTel Collector |

### Recovery Priority

```
Priority 0 (immediate):
  API Layer + Runtime Engine  →  restore service first
  Gateway                      →  restore tool access

Priority 1 (within RTO):
  Redis Streams                →  restore event delivery
  Checkpoint Repository        →  restore state durability

Priority 2 (best effort):
  OTel Pipeline                →  restore observability
```

---

## 3. Recovery Procedures

### DR-01: Redis Recovery

```
1. DETECT
   - Alert: RedisPublishErrors or ConsumerLagHigh
   - Confirm: check Redis connectivity from runtime pod

2. ASSESS
   - Can Redis be restarted in-place? → restart with existing volume
   - Is Redis volume corrupted? → restore from AOF/RDB backup
   - Is Redis completely gone? → provision new Redis instance

3. RESTORE
   a. If in-place restart:
      kubectl rollout restart deployment redis
      Wait for health check: redis-cli ping

   b. If backup restore:
      kubectl cp backup.aof redis-pod:/data/appendonly.aof
      kubectl delete pod redis-pod
      Wait for new pod to load AOF

   c. If new instance:
      kubectl apply -f deploy/k8s/redis-deployment.yaml
      Update kitematic-config ConfigMap with new Redis URL
      kubectl rollout restart deployment kitematic-api

4. VERIFY
   - Runtime can connect: check runtime logs for "Connected to Redis"
   - Events flow: publish a test event and verify consumer receives it

5. DECLARE RESOLVED
   - Error rate returns to baseline
   - All alerts clear
```

### DR-02: Checkpoint Integrity Recovery

```
1. DETECT
   - Alert: HighCheckpointErrorRate
   - Confirm: inspect `runtime.executions.failed` for checkpoint errors

2. ASSESS
   - Is corruption widespread or isolated to one checkpoint?
   - Can the affected execution be replayed from the beginning?

3. RESTORE
   a. If isolated corruption:
      Remove corrupted checkpoint file
      The runtime will create a new checkpoint on next save

   b. If index corruption:
      Rebuild index by scanning all checkpoint files:
      python scripts/rebuild_checkpoint_index.py --dir /data/checkpoints

   c. If full data loss:
      Restore checkpoint directory from backup
      Verify index consistency

4. VERIFY
   - Restore the most recent checkpoint
   - Verify state integrity: JSON decode + SHA-256 hash match
   - Run a test execution end-to-end

5. DECLARE RESOLVED
   - No more CheckpointPersistenceError in logs
   - New executions complete successfully
```

### DR-03: Runtime Pod Recovery

```
1. DETECT
   - K8s auto-restarts the pod (liveness probe failure)
   - Alert: RuntimeHighFailureRate or APIHighErrorRate

2. ASSESS
   - Check pod logs for crash reason: kubectl logs --previous pod/kitematic-api-xyz
   - Is another replica serving? Check HPA and replica status

3. RESTORE (K8s handles automatically)
   - If auto-recovery within 2 minutes: monitor only
   - If crash-loop: check liveness probe, resource limits, recent code changes

4. VERIFY
   - Readiness probe passes
   - API responds to /health
   - Executions complete successfully

5. DECLARE RESOLVED
   - All replicas healthy
   - No recent crash events
```

### DR-04: OTel Collector Recovery

```
1. DETECT
   - Alert: CollectorUnavailable
   - No new trace data in backend

2. ASSESS
   - Is collector process running?
   - Is network route from runtime to collector available?

3. RESTORE
   a. Restart collector:
      kubectl rollout restart deployment otel-collector
      or docker-compose restart otel-collector

   b. If config error:
      Check collector logs for config parse errors
      Verify OTLP endpoint configuration

4. VERIFY
   - Collector starts successfully
   - Runtime logs show "OTel exporter connected"
   - Test span reaches backend

5. DECLARE RESOLVED
   - Traces appearing in backend
   - No CollectorUnavailable alerts
```

### DR-05: Deployment Rollback

```
1. DETECT
   - CI pipeline failure (quality gate)
   - Alert: APIHighErrorRate or RuntimeHighFailureRate within 5 min of deploy

2. ASSESS
   - Is the error rate correlated with the new deployment?
   - Check deployment revision history: kubectl rollout history deployment/kitematic-api

3. RESTORE (automated)
   kubectl rollout undo deployment/kitematic-api
   Wait for rollout complete: kubectl rollout status deployment/kitematic-api

4. VERIFY
   - Error rate returns to pre-deployment baseline
   - All SLOs green

5. DECLARE RESOLVED
   - Previous stable revision serving
   - Post-mortem scheduled for deployment failure
```

---

## 4. DR Test Suite

Tests are in `tests/dr/` and run via `pytest tests/dr/ -v --tb=short`.

### Test Coverage

| Test ID | Scenario | What It Tests | Status |
|---|---|---|---|
| DR-T01 | Checkpoint corruption | JSON corruption + recovery | Implemented |
| DR-T02 | Checkpoint atomic write | Partial write safety | Implemented |
| DR-T03 | Runtime restart recovery | Re-initialization with tenant context | Implemented |
| DR-T04 | Checkpoint backup/restore | FileSystemRepository durability | Implemented |
| DR-T05 | OTel collector failover | SDK resilience (from P5.3) | Inherited |
| DR-T06 | Redis stream replay | Replay events after disconnect | Implemented |

### Running Tests

```bash
# All DR tests
pytest tests/dr/ -v --tb=short

# Specific scenario
pytest tests/dr/test_dr_checkpoint.py -v --tb=short

# With coverage
pytest tests/dr/ --cov=runtime --cov-report=term
```

### DR Test Implementation
