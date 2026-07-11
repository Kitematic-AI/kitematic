# Kitematic System Constitution

**Version:** 1.0
**Status:** CORE DOCTRINE (Immutable without unanimous ADR)

## Core Principles

### 1. Zero-Trust by Default
- No Agent, Adapter, or Tool is trusted by default.
- Every action requires policy evaluation before execution.
- All components must have a defined Trust Level (T0–T4).

### 2. No Side Effects
- Agents must not execute external operations directly.
- All side effects (API calls, data writes, file modifications) must be expressed as **Intents** and routed through the MCP Gateway.
- Direct execution violates the architecture.

### 3. Immutability & Time Travel
- Historical execution data (audit logs, checkpoints) is immutable.
- Recovery is done via checkpoint restore, not by modifying history.
- Every state change produces an append-only record.

### 4. Centralized Context
- Long-term memory is controlled by Kitematic Memory Service.
- Agents cannot directly modify or delete historical memory.
- All memory access must pass through governance.

### 5. Explicit Architecture
- No architectural change without an Architecture Decision Record (ADR).
- Every change must document context, decision, and consequences.

### 6. Every Action Must Be Replayable
- All production actions must be reconstructible from checkpoints and audit logs.
- Non-replayable actions are forbidden.

### 7. Every Tool Call Must Pass Through the Gateway Chain
```
Agent → Orchestrator → Policy Engine → MCP Gateway → Tool
```
Direct Agent-to-Tool communication is forbidden.

### 8. Historical Execution Data is Immutable
- No deletion or modification of execution history.
- Schema evolution through versioning only.

### 9. AI Builders Must Follow the Build Protocol
```
Read → Understand → Plan → Validate → Modify → Update Docs
```
No skipping steps.
