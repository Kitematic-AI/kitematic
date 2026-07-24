# Kitematic Runtime

**AI Operating System — secure, observable, multi-tenant execution layer.**

Kitematic is a production-grade runtime for AI agent execution with policy enforcement, OpenTelemetry observability, disaster recovery, and chaos engineering built-in.

---

## Quick Start

```bash
pip install -e ".[dev,redis,otel]"
kitematic-api
curl http://localhost:8000/api/v1/health
```

## Documentation

| Document | Description |
|---|---|
| [Architecture](docs/02_ARCHITECTURE/TAD.md) | Technical architecture design |
| [Deployment](docs/05_DEPLOYMENT/DEPLOYMENT.md) | Deployment guide |
| [API Contracts](docs/02_ARCHITECTURE/API_CONTRACTS.md) | API reference |
| [Monitoring & SLOs](docs/P5_MONITORING_SLO.md) | SLO framework, alerts, dashboards |
| [Disaster Recovery](docs/P5_DR_PLAN.md) | DR scenarios, RTO/RPO, runbooks |
| [Incident Response](docs/P5_INCIDENT_RESPONSE.md) | Incident classification, escalation, playbooks |
| [Chaos Engineering](docs/P5_CHAOS_ENGINEERING.md) | Chaos catalog, CI integration, guardrails |
| [Security](SECURITY.md) | Security policy, reporting vulnerabilities |
| [Release Checklist](docs/RELEASE_CHECKLIST.md) | Release validation gates |
| [Changelog](CHANGELOG.md) | Version history |

## Quick Reference

```bash
# Run all quality gates
make fast

# Run full test suite + chaos
make slow

# Run specific suites
python -m pytest tests/runtime/ -v
python -m pytest tests/dr/ -v
python -m pytest tests/chaos/ -v    # requires KITEMATIC_CHAOS_ENABLED=1
python -m pytest tests/integration/ -v
python -m pytest tests/performance/ -v
```

## Project Status

**Version**: 1.0.0-rc.1 — Release Candidate

| Aspect | Status |
|---|---|
| CI Quality Gates | ✅ ruff, mypy, pytest, coverage ≥ 90% |
| Security | ✅ pip-audit, bandit, Trivy |
| Observability | ✅ OTel traces, metrics, logs |
| SLOs | ✅ 13 SLIs, 7 SLOs, error budgets |
| Disaster Recovery | ✅ 6 scenarios, 18 tests |
| Incident Response | ✅ P0-P3, escalation, postmortem |
| Chaos Engineering | ✅ 27 experiments, nightly/weekly/pre-release |
| Container | ✅ Docker, SBOM, Trivy scan |

## License

Proprietary — see [LICENSE](LICENSE) for details.
