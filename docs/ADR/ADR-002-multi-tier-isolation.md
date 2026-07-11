# ADR-002: Multi-Tier Isolation Model

**Status:** ACCEPTED
**Date:** 2026-07-11

## Context

Different customers have different isolation requirements. A single isolation approach (e.g., shared namespace only) would either be too expensive for small users or too insecure for enterprises.

## Decision

Adopt a multi-tier isolation model instead of a single approach:

| Tier | Mode | Technology |
|------|------|-----------|
| 1 | Shared SaaS | K8s Namespace + Resource Quotas |
| 2 | Dedicated SaaS | Namespace + RBAC + Network Policies |
| 3 | Enterprise | vCluster / Dedicated Cluster |
| 4 | Air-Gapped | Private K8s + Firecracker + Offline |

Tenants are assigned a tier based on their plan. The architecture abstracts the tier from the Control Plane, meaning the same API works across all tiers.

## Consequences

**Positive:**
- Addresses the full market from indie to government.
- Tiers can be transparent to Agent developers.
- Scalable cost model aligned with customer value.

**Negative:**
- More complex infrastructure code.
- Testing must cover all four tiers.

## References

- `docs/05_DEPLOYMENT/DEPLOYMENT.md`
