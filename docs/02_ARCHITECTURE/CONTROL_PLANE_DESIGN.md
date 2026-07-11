# Kitematic Control Plane Design

Detailed design of the Control Plane's internal flow, state machine, and coordination logic.

## 1. Orchestrator: The Core State Machine

The Orchestrator is the heart of Kitematic. It receives commands from the Lifecycle Manager, coordinates step execution with Workers, evaluates policies, and manages checkpoints.

### Execution Flow

```
User/API
   |
   v
API Gateway ──→ Lifecycle Manager ──→ Orchestrator
                                           |
                     ┌─────────────────────┤
                     v                     v
              Policy Engine          Checkpoint Service
                     |                     |
                     v                     |
                 ALLOW/DENY                |
                                           v
                     ┌─────────────────────┘
                     v
              Worker Pool
                     |
           ┌────────┴────────┐
           v                 v
     MCP Gateway        Model Gateway
           |                 |
           v                 v
        Tools              LLMs
```

### Step Execution State Machine

```
                  ┌─────────────┐
                  │   PENDING   │
                  └──────┬──────┘
                         │ start
                         v
                  ┌─────────────┐
                  │  POLICY_CHECK│◄──────────── retry
                  └──────┬──────┘
                         │ allow
                         v
                  ┌─────────────┐
                  │   EXECUTING │
                  └──────┬──────┘
                    │    │    │
           ┌────────┘    │    └────────┐
           v             v             v
    ┌───────────┐ ┌───────────┐ ┌───────────┐
    │TOOL_NEEDED│ │APPROVAL_  │ │ COMPLETED │
    │           │ │REQUIRED   │ │           │
    └─────┬─────┘ └─────┬─────┘ └─────┬─────┘
          │             │             │
          v             v             v
   ┌────────────┐ ┌────────────┐ ┌────────────┐
   │MCP Gateway │ │Approval    │ │Checkpoint  │
   │Call Tool   │ │Service     │ │Save & Notify│
   └────────────┘ └────────────┘ └────────────┘
          │             │
          └──────┬──────┘
                 v
          ┌─────────────┐
          │  CHECKPOINT │
          └──────┬──────┘
                 v
          ┌─────────────┐      ┌─────────────┐
          │ NEXT STEP   │─────►│   FAILED    │
          └─────────────┘      └─────────────┘
```

## 2. Agent Registry Service

### Responsibilities
- Store and version Agent definitions (templates and instances).
- Validate Agent manifests against the Runtime Contract (RTC).
- Resolve compatibility between Agent requirements and available adapters.

### Versioning Strategy
- Each Agent definition is versioned (semver).
- When an Agent is updated, a new version record is created; old versions remain accessible.
- Rollback is supported by re-deploying a previous version.

### Template → Instance Model
- **Templates** are reusable blueprints (e.g., "Financial Analyst Agent").
- **Instances** are deployed copies of a template with concrete configuration (tenant-specific settings, tool permissions, model routing).

## 3. Lifecycle Manager

### Responsibilities
- Map user commands (start, stop, pause, resume) into Orchestrator actions.
- Track execution status across the entire lifecycle.
- Manage scaling decisions (how many Worker replicas per Agent).

### Lifecycle State Machine

```
 DRAFT ──► PENDING ──► RUNNING ──► COMPLETED
               │           │
               ▼           ▼
           FAILED       PAUSED
                          │
                          ▼
                       RESUMING ──► RUNNING
```

### Commands
| Command | Effect |
|---------|--------|
| `start` | Create execution, assign to Orchestrator |
| `stop` | Kill execution, save final checkpoint |
| `pause` | Request checkpoint, pause orchestration |
| `resume` | Restore from checkpoint, resume orchestration |
| `scale` | Adjust Worker pool size for this Agent |

## 4. Policy Engine

### Responsibilities
- Evaluate every action request against defined policies.
- Maintain audit trail of all decisions.
- Support complex conditions (CEL expressions).

### Evaluation Flow

```
Request (Agent, Action, Resource)
            │
            v
    ┌──────────────┐
    │ Load Policies │
    │ for Tenant   │
    └──────┬───────┘
           v
    ┌──────────────┐
    │ Evaluate     │
    │ Deny Rules   │──► DENY ←─ log & return
    └──────┬───────┘
           v (no deny match)
    ┌──────────────┐
    │ Evaluate     │
    │ Require      │──► REQUIRE_APPROVAL ←─ create approval request
    │ Approval     │
    └──────┬───────┘
           v (no approval match)
    ┌──────────────┐
    │ Evaluate     │
    │ Allow Rules  │──► ALLOW ←─ log & return
    └──────┬───────┘
           v (no allow match)
       DEFAULT_DENY ←─ log & return
```

## 5. Human Approval Service

### Flow

```
1. Policy Engine returns REQUIRE_APPROVAL
2. Approval Service creates approval_request (status: PENDING)
3. Orchestrator pauses execution
4. Notification sent to designated approvers
5. Approver reviews via API/Dashboard
6. Approval Service updates status (APPROVED / REJECTED)
7. Orchestrator resumes or cancels execution
```

### Approval Tiers

| Tier | Risk Level | Approver | Timeout |
|------|-----------|----------|---------|
| Quick | LOW | Any team member | 1 hour |
| Standard | MEDIUM | Team lead | 4 hours |
| Sensitive | HIGH | Manager | 24 hours |
| Critical | CRITICAL | Security officer | 72 hours |
