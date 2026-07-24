# P5.4 — Production Monitoring & SLO Framework

## Table of Contents

1. [Service Catalog](#1-service-catalog)
2. [Service Level Indicators (SLIs)](#2-service-level-indicators-slis)
3. [Service Level Objectives (SLOs)](#3-service-level-objectives-slos)
4. [Error Budget](#4-error-budget)
5. [Alerting Rules](#5-alerting-rules)
6. [Dashboards](#6-dashboards)
7. [Runbook Links](#7-runbook-links)

---

## 1. Service Catalog

Five services are monitored. Each maps to a bounded context in the runtime architecture.

| Service | Owner | Criticality | Dependencies |
|---|---|---|---|
| **Runtime Engine** | Runtime Team | P0 | Policy, Gateway, Checkpoint |
| **API Layer** | Platform Team | P0 | Runtime Engine |
| **Gateway** | Integration Team | P1 | MCP Servers |
| **Redis Streams** | Infrastructure Team | P1 | Redis Cluster |
| **OpenTelemetry Pipeline** | Observability Team | P2 | OTel Collector |

### Service Boundaries

| Service | Code Location | Entry Point |
|---|---|---|
| Runtime Engine | `runtime/kitematic_runtime/runtime.py` | `execute_intent()` |
| API Layer | `runtime/kitematic_runtime/api/app.py` | FastAPI routes |
| Gateway | `runtime/kitematic_runtime/gateway.py` | `access_tool()` |
| Redis Streams | `runtime/kitematic_runtime/events/redis_streams.py` | `publish()` / `consume()` |
| OTel Pipeline | `runtime/kitematic_runtime/observability/` | `get_tracer_provider()` |

---

## 2. Service Level Indicators (SLIs)

### 2.1 Availability

Measured as the proportion of valid requests that complete successfully.

| SLI | Service | Data Source | Measurement |
|---|---|---|---|
| API success rate | API Layer | `api.intents_succeeded` / `api.intents_submitted` | Ratio over 5 min window |
| Runtime completion rate | Runtime Engine | `runtime.executions.completed` / `runtime.executions.total` | Ratio over 5 min window |
| Gateway success rate | Gateway | `gateway.tool.success` / (`gateway.tool.success` + `gateway.tool.mcp_failure`) | Ratio over 5 min window |
| Redis publish success | Redis Streams | (Implicit — no errors in `publish()`) | Binary per-request |
| OTel export success | OTel Pipeline | (Implicit — no crash in `BatchSpanProcessor`) | Binary per-export |

### 2.2 Latency

Measured from metrics histograms and trace durations.

| SLI | Service | Metric Source | Unit |
|---|---|---|---|
| P95 execution latency | Runtime Engine | `runtime.execution.duration_ms` histogram | ms |
| P99 execution latency | Runtime Engine | `runtime.execution.duration_ms` histogram | ms |
| P95 gateway latency | Gateway | `gateway.tool.duration_ms` histogram | ms |
| P99 gateway latency | Gateway | `gateway.tool.duration_ms` histogram | ms |
| Phase-level latency | All | Trace span durations from `ExecutionTracer` | ms |

### 2.3 Throughput

| SLI | Service | Metric Source | Unit |
|---|---|---|---|
| Requests per second | API Layer | `api.intents_submitted` rate | req/s |
| Active executions | Runtime Engine | Gauge from `runtime.executions.started` minus `runtime.executions.completed` | count |
| Gateway calls per second | Gateway | `gateway.tool.success` rate | calls/s |

### 2.4 Quality

| SLI | Service | Metric Source |
|---|---|---|
| Policy rejection rate | Runtime Engine | `runtime.policy.rejected` / `runtime.executions.total` |
| Capability denial rate | Runtime Engine | `runtime.capability.denied` / `runtime.executions.total` |
| Checkpoint error rate | Runtime Engine | `runtime.checkpoint.error` / `runtime.executions.total` |

### 2.5 System Health

| SLI | Service | Metric Source |
|---|---|---|
| Rate limit hits | Runtime Engine | `resource.rate_limit.hit` |
| Quota exceeded count | Runtime Engine | `resource.quota.exceeded` |
| Gateway registry miss rate | Gateway | `gateway.tool.registry_miss` / `gateway.tool.success` |
| Gateway client miss rate | Gateway | `gateway.tool.client_miss` / `gateway.tool.success` |

---

## 3. Service Level Objectives (SLOs)

### 3.1 Core SLOs

| SLI | Target Window | SLO | Error Budget / period | Priority |
|---|---|---|---|---|
| API Availability | 30 days | **99.9%** | 43m 12s | P0 |
| Runtime Execution Success | 30 days | **≥99.5%** | 3h 36m | P0 |
| P95 Execution Latency | 7 days | **<500 ms** | N/A (latency) | P0 |
| P99 Execution Latency | 7 days | **<1 s** | N/A (latency) | P1 |
| Gateway Success Rate | 30 days | **≥99.0%** | 7h 12m | P1 |
| P95 Gateway Latency | 7 days | **<200 ms** | N/A (latency) | P1 |
| Checkpoint Error Rate | 30 days | **<0.1%** | — | P2 |

### 3.2 Rationale

- **API 99.9%**: Matches industry standard for HTTP APIs; the API is a thin transport layer with no business logic, so 99.9% is achievable.
- **Runtime 99.5%**: Lower than API because runtime depends on Gateway + Policy which may fail due to external factors. The 0.5% error budget allows for planned maintenance and transient MCP failures.
- **P95 500ms / P99 1s**: Based on observed performance — typical executions complete in 2–50ms in the test suite. 500ms P95 leaves room for Gateway calls to slow MCP servers.
- **Gateway 99.0%**: Gateway depends on external MCP servers which the platform does not control. 99.0% accounts for upstream failures.

### 3.3 Future SLOs (not yet tracked)

These SLOs depend on metrics not yet instrumented. They are tracked as improvement items.

| SLI | Blocked By |
|---|---|
| Redis publish latency | No histogram for `xadd` duration |
| OTel pipeline drop rate | No counter for dropped spans |
| Consumer lag | No lag metric from Redis Streams |

---

## 4. Error Budget

### 4.1 Definition

Error Budget = (1 − SLO) × total requests in the window. When the error budget is exhausted, feature development freezes and engineering effort shifts to reliability.

| SLO | Error Budget (30-day) | Equivalent Downtime |
|---|---|---|
| 99.9% | 0.1% of requests | 43m 12s |
| 99.5% | 0.5% of requests | 3h 36m |
| 99.0% | 1.0% of requests | 7h 12m |

### 4.2 Error Budget Policy

| Threshold | Action |
|---|---|
| **50% consumed** | Team investigates root cause. Post-mortem scheduled if not already open. |
| **80% consumed** | Feature freeze declared. Only reliability work, bug fixes, and security patches. |
| **100% consumed** | SLO violation declared. Emergency response. RCA required within 5 business days. |

### 4.3 Burn Rate Alerting

| Burn Rate | Window | Alert | Severity |
|---|---|---|---|
| > 10x | 1 hour | **Critical**: Error budget would exhaust in ~3 days at this rate | Pager |
| > 5x | 6 hours | **Warning**: Error budget would exhaust in ~6 days | Ticket |
| > 2x | 24 hours | **Info**: Above-normal error rate — investigate during business hours | Slack |

---

## 5. Alerting Rules

All alerts are SLO-based. Raw metric thresholds exist only for capacity planning, not paging.

### 5.1 Critical Alerts (Pager)

| Alert | Condition | SLI | Runbook |
|---|---|---|---|
| `APIHighErrorRate` | `api.intents_failed / api.intents_submitted > 0.001` for 5 min | API Availability | [api-failure.md](../deploy/runbooks/api-failure.md) |
| `RuntimeHighFailureRate` | `runtime.executions.failed / runtime.executions.total > 0.005` for 5 min | Runtime Success | [runtime-failure.md](../deploy/runbooks/runtime-failure.md) |
| `HighP95Latency` | `p95(runtime.execution.duration_ms) > 500` for 10 min | Execution Latency | [latency.md](../deploy/runbooks/latency.md) |
| `GatewayHighFailure` | `gateway.tool.mcp_failure / (gateway.tool.success + gateway.tool.mcp_failure) > 0.01` for 5 min | Gateway Success | [gateway-failure.md](../deploy/runbooks/gateway-failure.md) |

### 5.2 Warning Alerts (Ticket)

| Alert | Condition | Runbook |
|---|---|---|
| `RuntimeP99LatencyWarning` | `p99(runtime.execution.duration_ms) > 1000` for 10 min | [latency.md](../deploy/runbooks/latency.md) |
| `HighPolicyRejectionRate` | `runtime.policy.rejected / runtime.executions.total > 0.1` for 15 min | [policy.md](../deploy/runbooks/policy.md) |
| `HighCheckpointErrorRate` | `runtime.checkpoint.error / runtime.executions.total > 0.001` for 15 min | [checkpoint.md](../deploy/runbooks/checkpoint.md) |
| `RedisPublishErrors` | Any `ResponseError` in `redis_streams.publish()` | [redis.md](../deploy/runbooks/redis.md) |
| `CollectorUnavailable` | OTel batch export failures > 10 in 5 min | [otel-collector.md](../deploy/runbooks/otel-collector.md) |

### 5.3 Informational Alerts (Slack)

| Alert | Condition |
|---|---|
| `ErrorBudget50p` | Error budget consumed ≥ 50% for any P0 SLO |
| `ErrorBudget80p` | Error budget consumed ≥ 80% for any P0 SLO |
| `HighRateLimitHits` | `resource.rate_limit.hit > 10/min` sustained for 15 min |
| `QuotaExceeded` | `resource.quota.exceeded > 5/min` sustained for 15 min |
| `GatewayRegistryMiss` | `gateway.tool.registry_miss` rate increase > 2x baseline |

### 5.4 Burn Rate Alerts

| Burn Rate | Condition | Severity |
|---|---|---|
| 10x burn | Error budget would exhaust in < 3 days at current rate | Critical |
| 5x burn | Error budget would exhaust in < 6 days at current rate | Warning |
| 2x burn | Error budget would exhaust in < 15 days at current rate | Info |

---

## 6. Dashboards

### 6.1 Executive Dashboard

Purpose: At-a-glance health for the on-call engineer and engineering management.

```
┌─────────────────────────────────────────────────────────────────────┐
│  KITEMATIC PRODUCTION — EXECUTIVE DASHBOARD                         │
├──────────────────┬──────────────────┬──────────────────┬────────────┤
│  API Availability │ Runtime Success  │ Gateway Success  │ Requests/s │
│  ┌────────────┐   │  ┌────────────┐  │  ┌────────────┐  │   ┌───┐   │
│  │  99.97%   │   │  │  99.82%   │  │  │  99.31%   │  │   │ 42│   │
│  │  (30d)    │   │  │  (30d)    │  │  │  (30d)    │  │   └───┘   │
│  └────────────┘   │  └────────────┘  │  └────────────┘  │         │
├──────────────────┴──────────────────┴──────────────────┴────────────┤
│  Error Budget Remaining                                             │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  API:   ████████████████████████████████████░░░  87%         │   │
│  │  Runtime: ████████████████████████████████░░░░░  82%         │   │
│  │  Gateway: ████████████████████████░░░░░░░░░░░░  64%         │   │
│  └──────────────────────────────────────────────────────────────┘   │
├──────────────────┬───────────────────────────────────────────────────┤
│  P95 Latency      │  Active Executions / Rate Limit Hits             │
│  ┌────────────────┐  ┌────────────────────────────────────────────┐  │
│  │  124ms         │  │  Active: 7  |  Rate limited: 3/min         │  │
│  │  P99: 387ms    │  │  Policy rejects: 12/hr | Failed: 2/hr      │  │
│  └────────────────┘  └────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

**Refresh**: 30 seconds. **Time range**: 1h default (30d for SLOs).

**Panels**:
1. **SLO Gauge** (×3 — API, Runtime, Gateway) — Sparkline + current % over 30d window
2. **Error Budget Remaining** (×3) — Horizontal bar with color: green > 80%, yellow > 50%, red < 50%
3. **Requests/sec** — Time series, 5 min avg
4. **P95/P99 Latency** — Stat panel with sparkline
5. **Active Executions** — Stat, current value
6. **Error Rates** — Per-service error count last 1h

---

### 6.2 Operations Dashboard

Purpose: Daily operations — queue depths, consumer health, runtime internals.

```
┌─────────────────────────────────────────────────────────────────────┐
│  KITEMATIC PRODUCTION — OPERATIONS DASHBOARD                        │
├──────────────────┬──────────────────┬──────────────────┬────────────┤
│  Runtime State   │  Queue Depth     │  Active Execs    │ Exec/s     │
│  ┌────────────┐  │  ┌────────────┐  │  ┌────────────┐  │  ┌────┐   │
│  │  RUNNING   │  │  │    142     │  │  │     12     │  │  │ 3.2│   │
│  └────────────┘  │  └────────────┘  │  └────────────┘  │  └────┘   │
├──────────────────┴──────────────────┴──────────────────┴────────────┤
│  Execution Latency Distribution (heatmap)                           │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  <100ms  ████████████████████████████████████████████  68%   │   │
│  │  100-300 ██████████████                              22%   │   │
│  │  300-500 ████                                          5%   │   │
│  │  500-1s  ██                                           3%   │   │
│  │  >1s     █                                            2%   │   │
│  └──────────────────────────────────────────────────────────────┘   │
├──────────────────┬──────────────────┬────────────────────────────────┤
│  Loop Health     │  Checkpoint      │  Rate Limit / Quota           │
│  ┌────────────┐  │  ┌────────────┐  │  ┌────────────────────────┐   │
│  │ Started: 87│  │  │ Save: 43ms │  │  │ Rate limit: 12/hr      │   │
│  │ Budget: 8 │  │  │ Error: 0%  │  │  │ Quota: 3/hr             │   │
│  │ Timeout: 0│  │  └────────────┘  │  └────────────────────────┘   │
│  └────────────┘  │                 │                                │
└─────────────────────────────────────────────────────────────────────┘
```

**Refresh**: 10 seconds. **Time range**: 1h default.

**Panels**:
1. **Runtime State** — Current `RuntimeState` enum value
2. **Event Queue Depth** — Current pending events queue size
3. **Active Executions** — Current count
4. **Execution Latency Distribution** — Histogram with buckets
5. **Loop Health** — Counters for loop started/completed/budget/timeout
6. **Checkpoint** — Average duration + error count
7. **Rate Limit / Quota** — Current hit counters

---

### 6.3 Debug Dashboard

Purpose: Deep-dive investigation — traces, slow executions, gateway internals.

```
┌─────────────────────────────────────────────────────────────────────┐
│  KITEMATIC PRODUCTION — DEBUG DASHBOARD                             │
├─────────────────────────────────────────────────────────────────────┤
│  Recent Trace Phases (last 50 executions)                           │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Intent → Policy → Capability → Route → Tool → Chkpt → Done │   │
│  │  Phase durations: [2ms→1ms→0.5ms→1ms→45ms→3ms→0.5ms]        │   │
│  │  FAILED at Tool: Gateway timeout after 30s                   │   │
│  │  FAILED at Policy: capability check rejected action 'delete' │   │
│  └──────────────────────────────────────────────────────────────┘   │
├──────────────────┬──────────────────────────────────────────────────┤
│  Slow Executions │  Gateway Calls                                   │
│  ┌────────────────┐  ┌──────────────────────────────────────────┐   │
│  │ exec-123: 1.2s │  │  tool1.server1: 45ms  (success)          │   │
│  │ exec-456: 0.9s │  │  tool2.server1: 30ms  (success)          │   │
│  │ exec-789: 0.7s │  │  tool3.server2: ERROR (timeout)          │   │
│  └────────────────┘  └──────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│  Logs — Real-time tail filtered by execution_id                    │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 12:00:01 INFO  Execution started  exec=exec-123              │   │
│  │ 12:00:02 INFO  Tool access success tool=search exec=exec-123 │   │
│  │ 12:00:03 WARN  Budget exhausted steps=25 exec=exec-456       │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

**Refresh**: Real-time (WebSocket push for logs). **Time range**: 30m default.

**Panels**:
1. **Trace Waterfall** — Each execution phase as a horizontal bar with timing
2. **Slow Execution List** — Top 10 by duration, clickable to open trace
3. **Gateway Call Log** — Table: tool, server, duration, status
4. **Log Tail** — Real-time log stream with execution_id filter
5. **Error Breakdown** — Pie chart: policy rejections vs capability denials vs gateway errors vs checkpoint errors

---

## 7. Runbook Links

Every alert MUST contain a direct link to its runbook. Runbooks are stored in `deploy/runbooks/`.

| Alert | Runbook | Content Summary |
|---|---|---|
| `APIHighErrorRate` | [api-failure.md](../deploy/runbooks/api-failure.md) | Check FastAPI workers, restart API, verify DB connection |
| `RuntimeHighFailureRate` | [runtime-failure.md](../deploy/runbooks/runtime-failure.md) | Check `runtime.executions.failed` breakdown, inspect logs for `error` field |
| `HighP95Latency` | [latency.md](../deploy/runbooks/latency.md) | Identify slow phase via traces, check Gateway duration histogram |
| `GatewayHighFailure` | [gateway-failure.md](../deploy/runbooks/gateway-failure.md) | Check MCP server health, inspect `gateway.tool.mcp_failure` |
| `HighPolicyRejectionRate` | [policy.md](../deploy/runbooks/policy.md) | Review recent policy changes, check `runtime.policy.rejected` reason |
| `RedisPublishErrors` | [redis.md](../deploy/runbooks/redis.md) | Check Redis cluster health, verify consumer groups |
| `CollectorUnavailable` | [otel-collector.md](../deploy/runbooks/otel-collector.md) | Restart OTel Collector, verify OTLP endpoint, confirm no data loss |

### Alert-to-Runbook Mapping (Prometheus Alertmanager format)

```yaml
groups:
  - name: kitematic-slo
    rules:
      - alert: APIHighErrorRate
        expr: |
          rate(api_intents_failed[5m])
          /
          rate(api_intents_submitted[5m])
          > 0.001
        for: 5m
        annotations:
          summary: "API error rate above SLO threshold"
          runbook: "https://github.com/kitematic/runbooks/blob/main/api-failure.md"

      - alert: RuntimeHighFailureRate
        expr: |
          rate(runtime_executions_failed[5m])
          /
          rate(runtime_executions_total[5m])
          > 0.005
        for: 5m
        annotations:
          summary: "Runtime failure rate above SLO threshold"
          runbook: "https://github.com/kitematic/runbooks/blob/main/runtime-failure.md"

      - alert: HighP95Latency
        expr: |
          histogram_quantile(0.95,
            rate(runtime_execution_duration_ms_bucket[10m])
          ) > 500
        for: 10m
        annotations:
          summary: "P95 execution latency exceeds 500ms SLO"
          runbook: "https://github.com/kitematic/runbooks/blob/main/latency.md"

      - alert: GatewayHighFailure
        expr: |
          rate(gateway_tool_mcp_failure[5m])
          /
          (rate(gateway_tool_success[5m]) + rate(gateway_tool_mcp_failure[5m]))
          > 0.01
        for: 5m
        annotations:
          summary: "Gateway failure rate above SLO threshold"
          runbook: "https://github.com/kitematic/runbooks/blob/main/gateway-failure.md"
```

---

## Production Monitoring Guide

### How to Use This System

1. **Start with the Executive Dashboard** — Check SLO compliance and error budget for a 30-second health assessment.
2. **Drill down to Operations** — If an SLO is burning, go to the Operations Dashboard to inspect queue depths, latencies, and active executions.
3. **Debug with traces** — For slow or failed executions, use the Debug Dashboard to trace the exact phase and find the root cause.
4. **Respond to alerts** — Every alert has a runbook link. Follow the runbook before escalating.

### On-Call Rotation

- **Primary**: Receives Critical alerts via pager. 15-minute response time SLA.
- **Secondary**: Receives Warning alerts via ticket. 4-hour response time SLA.
- **Business hours**: Info alerts via Slack. Next-business-day response.

### SLO Review Cadence

| Review | Frequency | Participants |
|---|---|---|
| Error budget check | Daily standup | On-call engineer |
| Burn rate review | Weekly | Platform team |
| SLO adjustment | Quarterly | All engineering |
| Post-mortem for SLO violations | After each violation | Root cause owner |

### Known Gaps (Future Instrumentation)

| Gap | Impact | Planned Resolution |
|---|---|---|
| No Redis consumer lag metric | Cannot SLO on stream processing | Add lag gauge to `redis_streams.py` |
| No OTel drop rate counter | Cannot SLO on observability pipeline | Add counter to `BatchSpanProcessor` callback |
| No histogram for checkpoint duration | Cannot SLO on checkpoint latency | Add `.record("checkpoint.duration_ms")` |
| No per-tenant metrics breakdown | Cannot detect noisy tenant | Add `tenant_id` label to all metrics |
