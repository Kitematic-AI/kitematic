# Forbidden Actions

The following actions are strictly prohibited at all times. Violation triggers immediate halt and human review.

## Data & State

- ❌ Deleting or modifying audit logs.
- ❌ Altering checkpoint history (append only; no update/delete).
- ❌ Storing secrets in the repository or configuration files.
- ❌ Sharing memory between tenants without explicit policy.

## Architecture

- ❌ Adding a new service without an ADR.
- ❌ Changing the runtime contract without versioning.
- ❌ Creating direct connections between architectural layers (e.g., Worker → DB).
- ❌ Bypassing the Policy Engine for any execution decision.

## Security

- ❌ Executing tools without a policy check.
- ❌ Making direct external API calls from Agent code (use MCP Gateway).
- ❌ Changing security layers without security review and ADR.

## Development Process

- ❌ Skipping the planning phase before coding.
- ❌ Modifying constitution files without human approval.
- ❌ Adding dependencies without a security scan.
- ❌ Changing a database schema without a migration plan.

## Violation Protocol

1. Execution halts immediately.
2. A checkpoint is saved.
3. Human review is required before any resume or rollback.
