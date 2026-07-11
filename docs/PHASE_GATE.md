# Kitematic Phase Gate

This file is the **sole authority** for phase transitions. No Agent may begin a phase unless this file explicitly marks it as `unlocked` with `approved_by_human: true`.

```yaml
current_phase: 1B-Design

phase_0:
  name: Foundation & Constitution
  status: completed
  approved_by_human: true

phase_1:
  name: Architecture & Core Services
  status: active
  sub_phases:
    phase_1A:
      name: Architecture Definition
      status: completed
      approved_by_human: true
    phase_1B_Design:
      name: Implementation Design
      status: completed
      approved_by_human: true
    phase_1B_Code:
      name: Core Services Implementation
      status: locked
      approved_by_human: false

phase_2:
  name: Runtime & Execution Plane
  status: locked
  approved_by_human: false

phase_3:
  name: MCP Gateway & Adapters
  status: locked
  approved_by_human: false

phase_4:
  name: Memory & Checkpoint Services
  status: locked
  approved_by_human: false

phase_5:
  name: Policy & Governance Engine
  status: locked
  approved_by_human: false

phase_6:
  name: Infrastructure & Deployment
  status: locked
  approved_by_human: false

phase_7:
  name: SDK & CLI
  status: locked
  approved_by_human: false

phase_8:
  name: Marketplace & Ecosystem
  status: locked
  approved_by_human: false
```

## Rules

1. No Agent may begin work on a phase unless `approved_by_human` is `true`.
2. No Agent may change this file without explicit human instruction.
3. When a phase is completed, the Agent updates `status` to `completed` and `approved_by_human` remains as set by human.
4. The `current_phase` field is updated only by the Agent after human approval of the next phase.
