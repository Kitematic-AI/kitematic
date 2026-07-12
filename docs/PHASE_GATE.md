# Kitematic Phase Gate

This file is the **sole authority** for phase transitions. No Agent may begin a phase unless this file explicitly marks it as `unlocked` with `approved_by_human: true`.

```yaml
current_phase: 3

phase_0:
  name: Foundation & Constitution
  status: completed
  approved_by_human: true

phase_1:
  name: Architecture & Core Services
  status: partially_completed
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
      status: active
      sub_phases:
        phase_1B_Code_0:
          name: Bootstrap Skeleton & Interfaces
          status: completed
          approved_by_human: true
        phase_1B_Code_1:
          name: Core Logic Implementation
          status: active
          sub_phases:
            phase_1B_Code_1A:
              name: Domain Models, Validation & Serialization
              status: completed
              approved_by_human: true
            phase_1B_Code_1B:
              name: Agent Registry (In-Memory Implementation)
              status: completed
              approved_by_human: true
            phase_1B_Code_1C:
              name: Control Plane Orchestration Logic
              status: completed
              approved_by_human: true
            phase_1B_Code_1D:
              name: Policy Evaluation Engine
              status: completed
              approved_by_human: true
            phase_1B_Code_1E:
              name: Integration & E2E Tests
              status: completed
              approved_by_human: true

phase_2:
  name: Runtime & Execution Plane
  status: active
  sub_phases:
    phase_2A:
      name: Runtime Engine (InMemoryRuntime)
      status: completed
      approved_by_human: true
    phase_2B:
      name: Checkpoint Service
      status: completed
      approved_by_human: true
    phase_2C:
      name: Memory Service
      status: completed
      approved_by_human: true
    phase_2D:
      name: Execution Context Expansion
      status: completed
      approved_by_human: true
    phase_2E:
      name: Runtime ↔ Control Plane Integration
      status: completed
      approved_by_human: true

phase_3:
  name: MCP Gateway & Adapters
  status: unlocked
  approved_by_human: true

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
