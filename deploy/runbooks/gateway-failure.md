# Runbook: Gateway High Failure Rate

**Alert**: `GatewayHighFailure`
**Severity**: Critical (Pager)
**SLO**: Gateway Success Rate ≥ 99.0%

## Symptoms
- `gateway.tool.mcp_failure` rate > 1% of total gateway calls

## Possible Causes

| Cause | Probability | Detection |
|---|---|---|
| MCP server unreachable | High | `gateway.tool.mcp_failure` single-server spike |
| MCP client pool exhausted | Medium | Connection errors across all servers |
| Protocol mismatch | Low | After MCP server upgrade |

## Steps

1. Identify the failing MCP server from gateway logs
2. Check MCP server health (if external, contact vendor)
3. Restart MCP client connection
4. If all servers failing, check network connectivity

## Recovery
- Restart MCP client or gateway service
- Remove failing MCP server from routing if vendor issue
