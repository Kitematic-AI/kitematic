# Phase 1B Code Checklist

Before any commit that modifies `services/` or `runtime/`, every item below must be verified.

## Architecture Integrity

- [ ] All interfaces frozen (no signature changes without ADR)
- [ ] Contracts versioned (`runtime_contract_version` field present)
- [ ] Domain layer must not import infrastructure layer
- [ ] No implementation may bypass defined interfaces
- [ ] Dependency direction validated: `services/` → `runtime/contracts/` (not reverse)

## Code Quality

- [ ] No `pass` statement in non-test files
- [ ] No `raise NotImplementedError` in non-test files
- [ ] No `# TODO`, `# FIXME`, `# HACK` in non-test files
- [ ] No hardcoded configuration values
- [ ] No secrets or API keys in code

## Testing

- [ ] Every public method has a corresponding unit test
- [ ] Contract tests exist for each interface
- [ ] Breaking contract changes require an ADR before merge
- [ ] Tests pass before commit

## Data Access

- [ ] No direct database access from Control Plane code
- [ ] All data access goes through repository interface
- [ ] Repository interface returns domain models (not raw dicts)
- [ ] Repository owns persistence only, not business decisions
- [ ] Repository must not mutate domain rules
- [ ] Repository returns validated domain objects
- [ ] Repository contract tests are storage-independent

## Domain API Stability

- [ ] Domain public APIs are versioned
- [ ] Domain objects expose stable serialization format
- [ ] Domain validation errors are documented

## Violation Protocol

Any violation of the above blocks the commit. The offending code must be fixed before proceeding. If the checklist itself needs modification, an ADR is required.
