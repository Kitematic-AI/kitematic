# Runbook: OTel Pipeline Failure

## Detection
- Alert: `CollectorUnavailable`
- Symptom: No new trace/metric/log data in backend, gaps in dashboards

## Severity Assessment
| Finding | Severity |
|---|---|
| No observability data for 10+ min | P2 |
| Partial data loss (e.g., traces only) | P3 |
| Collector crash-looping | P2 |

## Immediate Actions
1. Check Collector pod status:
   ```bash
   kubectl get pods -l app=otel-collector
   ```
2. Check Collector logs:
   ```bash
   kubectl logs -l app=otel-collector --tail=50
   ```
3. Verify OTLP endpoint:
   ```bash
   curl -v telnet://otel-collector-service:4317
   ```
4. If config error: fix config and restart
5. If process crash:
   ```bash
   kubectl rollout restart deployment otel-collector
   ```

## Verification
- Collector starts and accepts connections
- Test span reaches backend via Debug Dashboard
- `kubectl logs -l app=otel-collector` shows no errors

## Rollback
```bash
kubectl rollout undo deployment otel-collector
```

## Escalation
| Condition | Escalate To |
|---|---|
| Collector down > 30 min | Observability team |
| Config corruption | Platform lead |

## Recovery Criteria
- Collector healthy for 10 minutes
- Traces appearing in backend
- Metrics being recorded
- No gaps > 5 minutes in telemetry data
