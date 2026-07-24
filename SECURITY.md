# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Kitematic Runtime, please report it confidentially.

**Do not open public GitHub issues for security vulnerabilities.**

### Contact

- **Email**: security@kitematic.dev
- **PGP Key**: Available on request — email security@kitematic.dev
- **Response SLA**: Initial acknowledgment within 48 hours

### Disclosure Policy

1. Report received → acknowledgment within 48 hours
2. Triage → severity assessment within 5 business days
3. Fix → patch released within 30 days for HIGH/CRITICAL
4. Disclosure → coordinated public disclosure after fix is available

### What to Include

- Description of the vulnerability
- Steps to reproduce (PoC preferred)
- Affected versions
- Potential impact
- Any suggested fix (if available)

## Security Architecture

| Layer | Mechanism | Documentation |
|---|---|---|
| Authentication | API key with SHA-256 fingerprinting, constant-time comparison | `runtime/kitematic_runtime/api/auth.py` |
| Authorization | Policy engine with capability checks | `runtime/domain/policy.py` |
| Tenant Isolation | `IsolationBoundary`, per-tenant quota | `runtime/kitematic_runtime/isolation.py` |
| Audit Logging | Security events (auth, key rotation) | `runtime/kitematic_runtime/api/audit.py` |
| Secrets | Key fingerprinting only — raw keys discarded after storage | `runtime/kitematic_runtime/config/secrets.py` |
| Dependency Security | `pip-audit` scanning, pinned versions | `pyproject.toml` |

## Scanning

| Tool | Scope | Frequency |
|---|---|---|
| pip-audit | Python dependency vulnerabilities | Every PR + nightly |
| bandit | AST security scan | Every PR + nightly |
| Trivy | Container image vulnerabilities | Nightly + release |

## Supported Versions

| Version | Supported |
|---|---|
| 1.0.0-rc.x | ✅ Active RC cycle |
| < 1.0.0 | ❌ Pre-release, not supported |

## Security Boundaries

See [Security Boundaries](docs/02_ARCHITECTURE/SECURITY_BOUNDARIES.md) for detailed architecture documentation.
