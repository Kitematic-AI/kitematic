# Runtime Contract (RTC v1.0)

The Linux ABI for AI Agents — defines how Agents communicate with Kitematic.

## 1. Runtime Identity

Every Runtime must declare itself:

```json
{
  "runtime_id": "langgraph-runtime-001",
  "framework": "langgraph",
  "version": "2.0",
  "capabilities": ["state_checkpoint", "tool_interception", "streaming"],
  "compatibility": { "kitematic_runtime_version": ">=1.0" }
}
```

## 2. Step Execution Contract

Agents execute one step at a time via the `step()` function:

### Request

```json
{
  "execution_id": "run_123",
  "goal": "Analyze sales data",
  "state": {},
  "memory_context": [],
  "permissions": {
    "tools": ["salesforce.read"],
    "models": ["azure.gpt"]
  },
  "budget": { "tokens": 50000, "time_seconds": 3600 }
}
```

### Response (Yields)

The Agent must return one of the following event types:

| Type | Description |
|------|-------------|
| `TOOL_REQUEST` | Needs to call a tool via MCP Gateway |
| `APPROVAL_REQUIRED` | Needs human approval before proceeding |
| `CHECKPOINT_REQUIRED` | Requests state save before sensitive action |
| `COMPLETED` | Task finished with final result |
| `FAILED` | Error occurred with error details |

## 3. Tool Invocation Contract

```json
{
  "type": "TOOL_REQUEST",
  "tool": { "provider": "mcp", "server": "salesforce", "name": "query" },
  "arguments": { "query": "SELECT revenue FROM Q4" }
}
```

## 4. Memory Contract

No direct memory writes from Agent code. Must emit:

```json
{
  "type": "MEMORY_WRITE",
  "memory_type": "FACT",
  "content": "User prefers deployment on AWS.",
  "confidence": 0.95
}
```

## 5. No Side Effects Rule

**Forbidden:** Direct API calls, database writes, file system access from Agent code.
**Allowed ONLY:** Emitting Intents (TOOL_REQUEST, MEMORY_WRITE, CHECKPOINT_REQUIRED) for Kitematic to execute.

## 6. Capability Negotiation

Before execution, Kitematic asks: "What capabilities do you support?"

```json
{ "supports_checkpoint": true, "supports_pause": true, "supports_streaming": true }
```

Enterprise policies may restrict execution if required capabilities are missing.

## 7. Transaction Model

Every step is a transaction:

```
BEGIN → Policy Check → Execute → Checkpoint → COMMIT / ROLLBACK
```

## 8. Error Contract

```json
{
  "type": "RUNTIME_ERROR",
  "category": ["TIMEOUT", "POLICY_DENIED", "TOOL_FAILURE", "MEMORY_FAILURE"],
  "recoverable": true,
  "recommended_action": "retry_from_checkpoint"
}
```

## 9. Versioning

All contracts must carry version information:

```json
{
  "runtime_contract_version": "1.0",
  "schema_version": "1.0",
  "adapter_api_version": "1.0"
}
```
