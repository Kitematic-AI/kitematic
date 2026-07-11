# Architecture Guardian

The Architecture Guardian is the automated gate that prevents architectural violations during development.

## Guardian Responsibilities

1. **Pre-Commit Validation** — Inspect all changes before they are committed.
2. **Pattern Enforcement** — Reject code patterns that violate the constitution.
3. **Boundary Checking** — Verify that no layer crosses its allowed boundaries.

## Pre-Commit Checks

### Database Access
- **Reject** `worker.query(postgres)`, `worker.execute(sql)`, or any direct data access from Execution Plane.
- **Allow** Only `Intent(type="DATA_REQUEST")` through Control Plane.

### External Calls
- **Reject** `requests.post(...)`, `http.client(...)`, or any direct HTTP call from Agent/Worker code.
- **Allow** Only `MCPGateway.execute(tool=...)` calls.

### Secrets Handling
- **Reject** Hardcoded API keys, passwords, tokens in code or configuration.
- **Allow** Only `vault.get_secret(...)` or Secrets Manager references.

### Architectural Layer Isolation
- **Reject** Imports or calls that cross architectural planes incorrectly.
- Example: Worker importing a database driver directly.

## Guardian Response

| Result | Action |
|--------|--------|
| **Pass** | Allow commit/execution to proceed. |
| **Warning** | Allow but log for human review. |
| **Fail** | Block commit. Provide reason and reference to the violated rule. |

## Override

The only way to override a Guardian rejection is via a signed ADR that explicitly addresses the violation and provides an approved exception.
