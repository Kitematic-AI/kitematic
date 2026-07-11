# AI Agent Build Rules

Mandatory protocol for any AI Builder Agent working on Kitematic.

## 1. The Builder Workflow

Every change must follow this exact sequence:

```
Read     →  Understand  →  Plan  →  Validate  →  Modify  →  Update Docs
```

### Step-by-step

1. **READ** — Load `CURRENT_STATE.md`, relevant constitution files, and Architecture Decisions.
2. **UNDERSTAND** — Confirm the context and confirm no conflicts with higher Level sources.
3. **PLAN** — Produce an explicit written plan before any code change. The plan must include:
   - Which files will be modified or created.
   - Architectural impact assessment.
   - Security considerations.
4. **VALIDATE** — Run the plan through the Architecture Guardian checks.
5. **MODIFY** — Execute only the changes in the approved plan. Do not exceed scope.
6. **UPDATE** — Update `CURRENT_STATE.md` and any affected documentation.

## 2. Agent Confidence Gate

Before starting any modification, the Builder Agent must confirm:

```json
{
  "understood_requirement": true,
  "architecture_impact_known": true,
  "security_review_done": true,
  "breaking_change": false
}
```

If any value is `false`, execution stops.

## 3. Separation of Duties

Three distinct roles in the build process:

| Role | Responsibility | Authority |
|------|---------------|-----------|
| **Planner** | Analyzes requirements, produces implementation plan | Cannot write code |
| **Reviewer** | Validates plan against constitution and architecture | Cannot write code |
| **Builder** | Executes approved plan | Cannot make architectural decisions |

## 4. Scope Discipline

- Execute only the assigned phase or task.
- Do not expand scope without explicit approval.
- Do not add features, services, or infrastructure outside the defined task.

## 5. Context Boundaries

- The `docs/` directory is the source of truth.
- Chat history is secondary and must not override documented decisions.
- If a conflict arises between conversation and documentation, documentation wins.
