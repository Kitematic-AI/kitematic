# P5.7 — Chaos Engineering

## Table of Contents

1. [Chaos Test Catalog](#1-chaos-test-catalog)
2. [Execution Levels](#2-execution-levels)
3. [Safety Guardrails](#3-safety-guardrails)
4. [Success Criteria](#4-success-criteria)
5. [Experiment Results](#5-experiment-results)
6. [CI/CD Integration](#6-cicd-integration)
7. [Quality Metrics](#7-quality-metrics)

---

## 1. Chaos Test Catalog

### Runtime (CHAOS-RT)

| ID | Experiment | Description | Level | Safety |
|---|---|---|---|---|
| CHAOS-RT-01 | Policy engine rejection spike | Simulate 100% policy rejection, verify graceful degradation | Nightly | Timeout 30s |
| CHAOS-RT-02 | Gateway intermittent failure | 50% gateway failure rate, verify retry + fallback | Nightly | Timeout 30s |
| CHAOS-RT-03 | Runtime restart under load | Restart runtime mid-execution, verify checkpoint recovery | Weekly | Timeout 60s |
| CHAOS-RT-04 | Concurrent tenant saturation | 50 concurrent tenants, verify isolation and fairness | Pre-release | Timeout 120s |
| CHAOS-RT-05 | Drain + stop mid-flight | Drain while executions in flight, verify clean shutdown | Nightly | Timeout 30s |
| CHAOS-RT-06 | Orphaned checkpoint cleanup | Simulate partial saves, verify GC doesn't lose data | Weekly | Timeout 60s |

### Redis (CHAOS-RD)

| ID | Experiment | Description | Level | Safety |
|---|---|---|---|---|
| CHAOS-RD-01 | Redis connection drop | Simulate connection loss, verify memory fallback | Nightly | Timeout 30s |
| CHAOS-RD-02 | Redis replay after disconnect | Publish, disconnect, reconnect, verify replay | Weekly | Timeout 60s |
| CHAOS-RD-03 | Consumer group rebalance | Simulate consumer death, verify group takeover | Pre-release | Timeout 120s |
| CHAOS-RD-04 | Stream corruption | Corrupt stream entry, verify skip + recovery | Nightly | Timeout 30s |

### Network (CHAOS-NW)

| ID | Experiment | Description | Level | Safety |
|---|---|---|---|---|
| CHAOS-NW-01 | Gateway timeout | Simulate MCP server timeout, verify client timeout handling | Nightly | Timeout 30s |
| CHAOS-NW-02 | Latency injection | Inject 500ms latency on all tool calls, verify SLO adherence | Weekly | Timeout 60s |
| CHAOS-NW-03 | Connection reset | Simulate TCP reset mid-request, verify reconnect | Pre-release | Timeout 120s |

### Storage / Checkpoint (CHAOS-ST)

| ID | Experiment | Description | Level | Safety |
|---|---|---|---|---|
| CHAOS-ST-01 | Checkpoint corruption | Corrupt checkpoint JSON, verify backup recovery | Nightly | Timeout 30s |
| CHAOS-ST-02 | Atomic write failure | Simulate partial checkpoint write, verify no corruption | Nightly | Timeout 30s |
| CHAOS-ST-03 | Checkpoint store full | Fill storage to capacity, verify graceful failure | Weekly | Timeout 60s |
| CHAOS-ST-04 | Concurrent checkpoint races | 10 concurrent saves to same execution, verify consistency | Pre-release | Timeout 120s |

### OpenTelemetry (CHAOS-OT)

| ID | Experiment | Description | Level | Safety |
|---|---|---|---|---|
| CHAOS-OT-01 | Collector unreachable | Drop OTLP connection, verify no runtime impact | Nightly | Timeout 30s |
| CHAOS-OT-02 | Span buffer overflow | Generate 10k spans rapidly, verify no memory leak | Weekly | Timeout 60s |
| CHAOS-OT-03 | Corrupted span data | Emit invalid span attributes, verify graceful handling | Nightly | Timeout 30s |

### API (CHAOS-AP)

| ID | Experiment | Description | Level | Safety |
|---|---|---|---|---|
| CHAOS-AP-01 | Auth key rotation storm | Rotate 100 keys simultaneously, verify no auth gaps | Weekly | Timeout 60s |
| CHAOS-AP-02 | Malformed requests | Send invalid JSON, oversized payloads, verify rejection | Nightly | Timeout 30s |
| CHAOS-AP-03 | Rate limit burst | Exceed rate limits, verify quota enforcement | Weekly | Timeout 30s |

### Kubernetes (CHAOS-K8 - simulated via mock)

| ID | Experiment | Description | Level | Safety |
|---|---|---|---|---|
| CHAOS-K8-01 | Pod restart simulation | Simulate pod death and recreation, verify runtime init | Weekly | Timeout 60s |
| CHAOS-K8-02 | ConfigMap reload | Simulate config change propagation, verify hot reload | Pre-release | Timeout 120s |

---

## 2. Execution Levels

| Level | Scope | When | CI Job | Safety |
|---|---|---|---|---|
| **PR** | No chaos | Every PR/push | CI only | N/A |
| **Nightly** | Light chaos (RT-01/05, RD-01/04, NW-01, ST-01/02, OT-01/03, AP-02) | 04:00 UTC daily | `nightly` chaos job | Timeout 30s |
| **Weekly** | Medium chaos (RT-03/06, RD-02, NW-02, ST-03, OT-02, AP-01/03, K8-01) | Sunday 04:00 UTC | `chaos-weekly` | Timeout 60s |
| **Pre-release** | Full chaos (all scenarios) | On tag push | `release` + manual | Timeout 120s |
| **Manual** | Any scenario on demand | `workflow_dispatch` | All workflows | Per scenario |

### Chaos Level Matrix

```
              PR    Nightly   Weekly   Pre-release   Manual
Runtime       ✗       ✓        ✓          ✓            ✓
Redis         ✗       ✓        ✓          ✓            ✓
Network       ✗       ✓        ✓          ✓            ✓
Storage       ✗       ✓        ✓          ✓            ✓
OTel          ✗       ✓        ✓          ✓            ✓
API           ✗       ✓        ✓          ✓            ✓
Kubernetes    ✗       ✗        ✓          ✓            ✓
```

---

## 3. Safety Guardrails

### Mandatory Guardrails

Every chaos experiment MUST:

1. **Environment check**: Verify `KITEMATIC_CHAOS_ENABLED` env var is set. Fail gracefully if not.
   ```python
   if not os.environ.get("KITEMATIC_CHAOS_ENABLED"):
       pytest.skip("Chaos experiments require KITEMATIC_CHAOS_ENABLED")
   ```

2. **Timeout**: Every experiment must have a pytest `timeout` marker.
   ```python
   @pytest.mark.timeout(30)
   ```

3. **Teardown**: Every experiment must clean up after itself (reset mocks, restore state).

4. **Isolation**: Experiments must not share mutable state. Use fresh fixtures per test.

5. **Read-only assertion**: Experiments must not modify production-adjacent resources.

6. **Fail open**: If the guardrail check itself fails, the experiment must be skipped (not failed).

### Environment Safety

| Env Var | Allowed Values | Purpose |
|---|---|---|
| `KITEMATIC_CHAOS_ENABLED` | `1`, `true` | Enable chaos experiments |
| `KITEMATIC_CHAOS_LEVEL` | `nightly`, `weekly`, `pre-release`, `manual` | Restrict to allowed scenarios |
| `KITEMATIC_ENV` | `dev`, `staging`, `prod` | Prevent chaos in production |

### Production Safeguards

```python
import os

def guard_production():
    env = os.environ.get("KITEMATIC_ENV", "dev")
    if env == "prod" and not os.environ.get("KITEMATIC_CHAOS_PROD_ALLOWED"):
        pytest.skip("Chaos experiments blocked in production")
```

---

## 4. Success Criteria

Every experiment must pass ALL applicable criteria to be considered successful:

| Criterion | Applicable To | Measure |
|---|---|---|
| ✅ Recovery within RTO | Runtime, Redis, Storage | Executions resume within configured RTO (default 30s) |
| ✅ Error budget not exceeded | All | Error rate < SLO error budget for recovery period |
| ✅ No data loss beyond RPO | Storage, Redis | Checkpoint count matches expected |
| ✅ Health checks pass | API, Runtime | Health endpoint returns 200 |
| ✅ Consumer groups recover | Redis | Consumer group re-established |
| ✅ No cascading failure | All | Failure in one component does not bring down others |

### Experiment Assertion Template

```python
result = ChaosResult(
    experiment_id="CHAOS-RT-01",
    start=start_time,
    duration=duration,
    expected="Policy rejection should not crash runtime",
    actual=f"Runtime healthy after {failure_count} rejections",
    metrics=metrics_snapshot,
    passed=all_criteria_met,
    logs=traceback.format_exc() if not all_criteria_met else "",
)
```

---

## 5. Experiment Results

### Result Schema

```python
@dataclass
class ChaosResult:
    experiment_id: str
    scenario: str
    level: str                      # nightly / weekly / pre-release / manual
    start_time: str                 # ISO 8601
    duration_seconds: float
    expected_outcome: str
    actual_outcome: str
    metrics_snapshot: dict          # key metric values at end of experiment
    passed: bool
    errors: list[str]
    logs: str                       # truncated log output
    recovery_rto_achieved: float | None   # seconds to recover
    recovery_rpo_achieved: int | None     # records lost (0 if none)
```

### Artifact Storage

Results are saved as JSON artifacts in CI:

```
chaos-results/
  nightly-2026-07-24/
    CHAOS-RT-01.json
    CHAOS-RD-01.json
    ...
    summary.json
  weekly-2026-07-27/
    ...
```

Each artifact is uploaded to GitHub Actions via `actions/upload-artifact`.

### Summary Report

A `summary.json` is generated after each run containing:

```json
{
  "timestamp": "2026-07-24T04:00:00Z",
  "level": "nightly",
  "total_experiments": 10,
  "passed": 9,
  "failed": 1,
  "flaky": 0,
  "mean_recovery_time_ms": 245.3,
  "recovery_variance_ms": 12.7,
  "chaos_success_rate": 0.90,
  "experiments": [
    {"id": "CHAOS-RT-01", "passed": true, "duration_s": 2.1},
    {"id": "CHAOS-RD-01", "passed": false, "duration_s": 5.3, "errors": ["Redis connection timeout exceeded RTO"]}
  ]
}
```

---

## 6. CI/CD Integration

### Workflow Architecture

```
                    ┌──────────────────┐
                    │   PR / Push      │
                    │   (ci.yml)       │
                    │   No Chaos       │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Nightly (04:00) │
                    │  Light Chaos     │
                    │  Report artifacts│
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Weekly (Sun)    │
                    │  Medium Chaos    │
                    │  Report artifacts│
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Pre-release     │
                    │  (tag push)      │
                    │  Full Chaos      │
                    │  Release Gate    │
                    └──────────────────┘
```

### Release Gate

The release pipeline (`release.yml`) includes a chaos gate:

```yaml
jobs:
  chaos-gate:
    name: Chaos Gate
    runs-on: ubuntu-latest
    steps:
      - run: echo "KITEMATIC_CHAOS_ENABLED=1" >> $GITHUB_ENV
      - run: pytest tests/chaos/critical/ -v --tb=short
```

**Gate policy**: If any critical chaos experiment fails, the release is blocked.

---

## 7. Quality Metrics

| Metric | Description | Target | Measured By |
|---|---|---|---|
| Chaos Success Rate | % of experiments passing | ≥ 95% | `summary.json` |
| Mean Recovery Time | Average time to recover across all experiments | < RTO | `chaos_success_rate` calculation |
| Recovery Variance | Std dev of recovery times | < 20% of mean | Per-experiment duration |
| Flaky Scenario Rate | % of experiments that pass intermittently | < 5% | Rolling 30-day window |
| Coverage | % of chaos catalog executed per level | 100% of assigned | CI matrix |

### Dashboard Integration

Metrics are exported to the Operations Dashboard:

- `chaos.experiments.total` — counter
- `chaos.experiments.passed` — counter
- `chaos.experiments.failed` — counter
- `chaos.recovery.time_ms` — histogram
- `chaos.success.rate` — gauge (rolling 7-day)

---

## Appendix: Experiment Runner

A `pytest`-based runner in `tests/chaos/conftest.py` provides:
- `ChaosResult` dataclass for structured output
- `chaos_experiment` fixture with guardrails, timing, and teardown
- `guard_production()` helper
- `write_chaos_artifact()` for CI artifact output
- `validate_recovery()` for RTO/RPO assertions
