# Change Control Process

## Architecture Change Lifecycle

Every architectural change must follow this path:

```
1. Change Request
        ↓
2. ADR Creation
        ↓
3. Impact Analysis
        ↓
4. Review & Approval
        ↓
5. Implementation
        ↓
6. Documentation Update
        ↓
7. Validation
```

## ADR Requirements

Each ADR must contain:

- **Title:** Clear description of the decision.
- **Context:** Why is this change needed? What problem does it solve?
- **Decision:** The actual architectural decision made.
- **Consequences:** What are the trade-offs? What breaks? What improves?
- **Status:** Proposed → Accepted → Rejected → Deprecated → Superseded.

## Approval Matrix

| Change Type | Requires |
|-------------|----------|
| Constitution modification | Unanimous ADR + Human approval |
| New service or component | ADR + Architecture Guardian review |
| API contract change | ADR + Versioning + Migration plan |
| Database schema change | ADR + Migration plan + Rollback plan |
| Security policy change | ADR + Security review |
| Dependency addition | Security scan + Compatibility check |
| Documentation only | No ADR required (direct update) |

## Breaking Changes

If a change is marked as **breaking**:

1. A migration path must be provided.
2. Old version must be supported for at least one deprecation cycle.
3. All consumers must be notified.

## Rollback Protocol

If a change causes issues after deployment:

1. Restore previous checkpoint.
2. Log the incident.
3. Create an ADR describing what went wrong and the fix.
