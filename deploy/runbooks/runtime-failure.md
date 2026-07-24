# Runbook: Runtime High Failure Rate

**Alert**: `RuntimeHighFailureRate`
**Severity**: Critical (Pager)
**SLO**: Runtime Execution Success ≥ 99.5%

## Symptoms
- `runtime.executions.failed / runtime.executions.total > 0.005` for 5 minutes

## Possible Causes

| Cause | Probability | Detection |
|---|---|---|
| Policy engine crash | Medium | `runtime.policy.rejected` or policy error logs |
| Gateway failure | High | `gateway.tool.mcp_failure` spike |
| Checkpoint error | Low | `runtime.checkpoint.error` spike |
| Internal exception | Medium | `error` field in `Loop halted unexpectedly` log |

## Steps

1. Check the failure breakdown: which counter drove the increase?
2. Inspect Debug Dashboard trace waterfall for the failing phase
3. Check `error` field in recent Execution log entries
4. If Gateway failure: follow gateway-failure.md
5. If Policy failure: review policy rules and evaluator health

## Recovery
- If Gateway: restart MCP client connections
- If Policy: reload policy rules from configuration
- If internal: capture stack trace, file bug, restart runtime
