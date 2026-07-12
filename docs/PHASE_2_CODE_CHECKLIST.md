# Phase 2 Code Checklist

Before any commit that modifies `runtime/execution/` or adds new runtime components, every item below must be verified.

## Runtime Isolation

- [ ] `runtime/execution/` must NOT import from `services/`
- [ ] `runtime/execution/` must NOT import from `infrastructure/`
- [ ] `runtime/execution/` may import from `runtime/contracts/` and `runtime/domain/`

## State Ownership

- [ ] Runtime does NOT transition the ExecutionStateMachine
- [ ] Runtime returns StepResponse — Control Plane applies state changes
- [ ] Runtime does NOT mutate input state (returns a copy)

## Determinism

- [ ] Same StepRequest + same ExecutionContext = same StepResponse
- [ ] No randomness or external time dependencies

## Resource Accounting

- [ ] Every executed step reports `tokens_consumed` in StepResponse
- [ ] Budget check happens BEFORE step execution
- [ ] `tokens_per_step` is configurable via ExecutionContext

## Code Quality

- [ ] No `pass` statement in non-test files
- [ ] No `raise NotImplementedError` in non-test files
- [ ] No `# TODO`, `# FIXME`, `# HACK` in non-test files
- [ ] No secrets or API keys in code
- [ ] No network/database/MCP/LLM calls

## Testing

- [ ] Every public method has a corresponding unit test
- [ ] Contract tests verify ABC compliance
- [ ] Budget exhaustion tests exist
- [ ] Invalid request tests exist
- [ ] No input mutation tests exist

## Dependencies

- [ ] `ExecutionContext` uses only stdlib types (int, str, dict, list)
- [ ] No external libraries required for runtime execution
