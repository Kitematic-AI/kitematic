# Emergency Control & Kill Switch

If the build process enters an unsafe state, this protocol activates.

## Trigger Conditions

Execution halts immediately when any of the following is detected:

1. **Infinite Loop** — Same operation repeated 3+ times without progress.
2. **Mass Modification** — More than 10 files changed in a single unplanned operation.
3. **Security Layer Change** — Any modification to authentication, authorization, or encryption logic.
4. **Guardian Bypass Attempt** — Code that attempts to circumvent an Architecture Guardian check.
5. **Scope Violation** — Building code, services, or infrastructure during Phase 0 (documentation only).

## Halt Protocol

```
1. Stop all operations immediately.
2. Save a builder checkpoint with current state.
3. Log the trigger reason with full context.
4. Set status to HALTED in CURRENT_STATE.md.
5. Request human intervention.
```

## Resume Conditions

Execution can only resume after:

- Human reviews the halt report.
- The root cause is identified and documented.
- A corrective action plan is approved.
- If the halt was triggered by a false positive, the guardian rules are updated via ADR.
