# ADR-001: Kitematic Agent Specification (KAS) Standard

**Status:** ACCEPTED
**Date:** 2026-07-11

## Context

Kitematic needs a standard packaging format for Agents and Adapters to ensure compatibility across the ecosystem. Without a standard, the marketplace will fragment and interoperability will break.

## Decision

Adopt the Kitematic Agent Specification (KAS) as the standard packaging format. Every Agent, Adapter, and Tool distributed through the Kitematic ecosystem must conform to KAS v1.0.

KAS includes:
- `manifest.json` — Identity, version, dependencies
- `policy.yaml` — Required permissions and trust level
- `runtime/` — Executable code
- `prompts/` — System prompts
- `metadata/signature.pem` — Cryptographic signature

## Consequences

**Positive:**
- Ecosystem-wide compatibility.
- Automated validation, scanning, and certification.
- Clear dependency and version management.

**Negative:**
- Existing Agents may need repackaging.
- Additional overhead for publishers (signatures, manifests).

## References

- `docs/06_ECOSYSTEM/ECOSYSTEM.md`
