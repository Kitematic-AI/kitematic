# Release Candidate Sign-off Checklist

**Must be completed before creating the v1.0.0 git tag.**

## Validation Artifacts

| Item | Value | Verified |
|---|---|---|
| **RC Validation CI Run ID** | `<run-id>` | ☐ |
| **Git Commit SHA** | `<sha>` | ☐ |
| **Docker Image Digest** | `<digest>` | ☐ |
| **SBOM Path** | `sbom.json` | ☐ |
| **Release Approver** | `<name>` | ☐ |
| **Staging Window** | `<start> → <end> UTC` | ☐ |

## CI Gates (rc-validation.yml)

| Gate | Status | CI Run URL |
|---|---|---|
| Code Quality (ruff + mypy) | ✅ / ❌ | |
| Tests + Coverage | ✅ / ❌ | |
| Security (pip-audit + bandit + license) | ✅ / ❌ | |
| Chaos Engineering (pre-release level) | ✅ / ❌ | |
| Disaster Recovery | ✅ / ❌ | |
| Performance | ✅ / ❌ | |
| Container Build + SBOM + Trivy | ✅ / ❌ | |

## Staging Validation (24h)

| Criteria | Result | Notes |
|---|---|---|
| 24h continuous runtime | ✅ / ❌ | |
| No crashes | ✅ / ❌ | |
| No memory leaks | ✅ / ❌ | |
| All SLOs within target | ✅ / ❌ | |
| No alert storms | ✅ / ❌ | |
| Rolling update verified | ✅ / ❌ | |
| Rollback verified | ✅ / ❌ | |

## Multi-role Review (RC-4.5)

| Area | Sign-off | Date |
|---|---|---|
| Architecture | ✅ / ❌ | |
| Security | ✅ / ❌ | |
| Operations | ✅ / ❌ | |
| Performance | ✅ / ❌ | |
| Documentation | ✅ / ❌ | |

## Final Approval

| Criterion | Met |
|---|---|
| No P0/P1 bugs open | ✅ / ❌ |
| Error budget not depleted | ✅ / ❌ |
| All chaos scenarios passed (critical) | ✅ / ❌ |
| All DR tests passed | ✅ / ❌ |

---

**Decision**: ☐ GO for v1.0.0  ☐ HOLD — create rc.2

**Release Manager**: _________________

**Date**: _________________

**Signature**: _________________
