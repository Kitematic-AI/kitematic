# Runbook: API High Error Rate

**Alert**: `APIHighErrorRate`
**Severity**: Critical (Pager)
**SLO**: API Availability ≥ 99.9%

## Symptoms
- Users receive 5xx responses
- Error rate > 0.1% sustained for 5 minutes

## Possible Causes

| Cause | Probability | Detection |
|---|---|---|
| FastAPI worker pool exhausted | High | `api.intents_failed` spike, no corresponding runtime failure |
| Runtime dependency unavailable | Medium | `api.intents_failed` correlates with `runtime.executions.failed` |
| Configuration error | Low | Recent deployment or config change |

## Steps

1. Check FastAPI worker count and restart if needed
2. Verify Runtime Engine health via `/health` endpoint
3. Inspect recent logs for `error` field in `Execution failed` entries
4. Check deployment status — was a new version recently rolled out?
5. If dependency issue, escalate to Runtime Engine runbook

## Recovery
- If worker exhaustion: increase `uvicorn` workers
- If dependency failure: follow runtime-failure.md
- If config error: rollback to previous config
