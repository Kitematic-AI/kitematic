# Runbook: Elevated Error Rate

## Detection
- Alert: Error rate > 2x baseline for any SLO
- Symptom: `runtime.executions.failed` or `gateway.tool.mcp_failure` spikes

## Severity Assessment
| Finding | Severity |
|---|---|
| Error rate > 10% of all requests | P1 |
| Error rate > 2x baseline but < 10% | P2 |
| Error rate slightly above baseline | P3 |

## Immediate Actions
1. Open Operations Dashboard → Error Rate panel
2. Categorize errors by type:
   - Policy rejections → check `PolicyEvaluator.evaluate_intent`
   - Gateway failures → check MCP servers in `ToolGateway`
   - Checkpoint errors → check persistence backend
   - Internal exceptions → check runtime logs
3. If deployment-related: rollback immediately (see rollback checklist)
4. If dependency-related: failover to secondary

## Verification
```
# Check error rate
runtime.executions.failed / runtime.executions.total < 0.001
```

## Rollback
```bash
kubectl rollout undo deployment/kitematic-api
kubectl rollout status deployment/kitematic-api
```

## Escalation
| Condition | Escalate To |
|---|---|
| Error rate > 10% for 15 min | Platform lead |
| Data corruption suspected | Engineering director |
| Customer impact confirmed | VP Engineering |

## Recovery Criteria
- Error rate within normal range for 15 minutes
- No repeated errors in logs
- All SLOs within target
