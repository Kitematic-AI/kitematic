# Source of Truth Hierarchy

Defines the priority of information sources for any Builder Agent.

## Priority Levels

### Level 0 — Immutable Constitution
`docs/00_CONSTITUTION/01_SYSTEM_CONSTITUTION.md`
- Non-negotiable laws of the system.
- Cannot be overridden by any lower level.

### Level 1 — Architecture Decisions
`docs/00_CONSTITUTION/06_ADR_PROCESS.md` and `docs/ADR/`
- Recorded Architecture Decision Records.
- Override lower levels but cannot contradict Level 0.

### Level 2 — Canonical Architecture
`docs/02_ARCHITECTURE/TAD.md`
`docs/04_DATA/DATA_MODEL.md`
`docs/03_CONTRACTS/RUNTIME_CONTRACT.md`
- The technical blueprint of the system.

### Level 3 — Current State
`docs/CURRENT_STATE.md`
- Where the project is now.
- Used for context, not for architectural authority.

### Level 4 — Task Instructions
The specific instructions given for the current operation.
- Must respect all higher levels.

### Level 5 — Conversation History
The chat or interaction history.
- Least authoritative.
- If conversation contradicts higher levels, higher levels win.

## The Rule

If an instruction from a lower level contradicts a higher level, execution must stop and an ADR must be requested before proceeding.
