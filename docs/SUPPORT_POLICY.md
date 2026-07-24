# Support Policy

## Supported Versions

| Version | Status | Support Level | End of Support |
|---|---|---|---|
| 1.0.x | ✅ Active | Full | Next MAJOR + 6 months |
| 1.x LTS | Planned | Extended TBD | TBD |
| < 1.0.0 | ❌ End of life | None | — |

## Support Levels

### Full Support
- Security patches within 30 days of disclosure
- Critical bug fixes within 14 days
- Standard bug fixes within next PATCH release
- Response via GitHub Issues within 48 hours (business days)

### Extended Support (LTS)
- Security patches only
- Critical bug fixes reviewed on case-by-case basis
- Response via GitHub Issues within 72 hours

### End of Life
- No patches or updates
- Users must upgrade to a supported version

## How to Get Support

| Channel | Use Case | Response Time |
|---|---|---|
| GitHub Issues | Bug reports, feature requests | 48 hours |
| Security email | Vulnerability disclosure | 48 hours (initial) |
| Documentation | Self-service troubleshooting | Always available |

## Bug Classification

| Severity | Definition | Response | Fix Target |
|---|---|---|---|
| P0 — Critical | Service outage, data loss | Immediate | 24 hours |
| P1 — High | Major feature broken | 4 hours | 7 days |
| P2 — Medium | Partial degradation | 24 hours | Next MINOR |
| P3 — Low | Cosmetic, non-urgent | 5 business days | Next PATCH |

## Backport Policy

- Security fixes: backported to last 2 MINOR releases
- Critical bug fixes: backported to last MINOR release
- Feature requests: not backported

## Deprecation Policy

1. Features marked as deprecated will continue to work for at least one MINOR version
2. Deprecation notice will be:
   - Logged at WARNING level at runtime
   - Documented in CHANGELOG
   - Called out in release notes
3. After the deprecation period, the feature will be removed in the next MAJOR version
