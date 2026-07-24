# Runbook: High Execution Latency

**Alert**: `HighP95Latency`
**Severity**: Critical (Pager)
**SLO**: P95 Execution Latency < 500ms

## Symptoms
- P95 latency > 500ms for 10 minutes
- Slow execution responses

## Steps

1. Open Debug Dashboard — check the trace waterfall
2. Identify which phase is slow (Tool execution is most common)
3. Check Gateway latency histogram (`gateway.tool.duration_ms`)
4. If Gateway is slow: identify the slow MCP server
5. If internal phase is slow: check system resources (CPU, memory, Redis)

## Recovery
- Scale Gateway workers if MCP calls are queued
- Add MCP server timeout if a server is hanging
- Scale Redis cluster if checkpoint/event latency is high
