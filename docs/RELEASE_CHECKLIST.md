# Release Checklist

## Pre-Release (RC-1 through RC-5)

### RC-1: Quality Freeze

- [ ] Version bumped to release candidate (e.g., `1.0.0-rc.1`)
- [ ] CHANGELOG.md updated with all changes since last release
- [ ] All dependency versions pinned in `pyproject.toml`
- [ ] No feature branches in progress — only bug fixes allowed
- [ ] No architectural changes pending

### RC-2: Verification Gate

- [ ] `ruff check runtime/ tests/` — 0 violations
- [ ] `mypy runtime/ --strict` — 0 errors
- [ ] `python -m pytest tests/` — 100% pass
- [ ] Coverage ≥ 90%
- [ ] `pip-audit --strict` — 0 vulnerabilities
- [ ] `bandit -r runtime/ -c .bandit.yaml -q` — 0 HIGH findings
- [ ] Chaos experiments: all pass at required level
- [ ] DR tests: all pass
- [ ] Performance tests: within budget
- [ ] Integration tests: all pass
- [ ] `docker build` — succeeds
- [ ] Trivy container scan — 0 CRITICAL/HIGH
- [ ] SBOM generated
- [ ] License audit completed — no incompatible licenses

### RC-3: Documentation Gate

- [ ] README.md — complete and accurate
- [ ] SECURITY.md — vulnerability reporting policy
- [ ] Architecture docs — up to date
- [ ] Deployment guide — up to date
- [ ] API reference — up to date
- [ ] Monitoring/SLO docs — up to date
- [ ] DR plan — up to date
- [ ] Incident response docs — up to date
- [ ] Chaos engineering docs — up to date
- [ ] RELEASE_NOTES_v{version}.md — written
- [ ] VERSIONING_POLICY.md — published
- [ ] SUPPORT_POLICY.md — published
- [ ] CHANGELOG.md — final review

### RC-4: Operational Validation

- [ ] 24-hour continuous runtime in staging
- [ ] No crashes or restarts during validation period
- [ ] No memory leaks detected
- [ ] No restart loops
- [ ] All SLOs within target for entire period
- [ ] No alert storms
- [ ] All dashboards populate correctly
- [ ] Trace/log/metric correlation verified
- [ ] Rolling update tested (no downtime)
- [ ] Rollback tested (no data loss)

### RC-4.5: Multi-role Review

- [ ] Architecture review signed off
- [ ] Security review signed off
- [ ] Operations review signed off
- [ ] Performance review signed off
- [ ] Documentation review signed off

### RC-5: Release Sign-off

- [ ] No P0/P1 bugs open
- [ ] All quality gates green
- [ ] Error budget not depleted
- [ ] All critical chaos scenarios passed
- [ ] All DR tests passed
- [ ] All documentation complete
- [ ] Artifact integrity verified:
  - [ ] Checksums generated
  - [ ] SBOM exported
  - [ ] Image digest recorded
  - [ ] Provenance/attestation created
- [ ] Git tag created: `v{version}`
- [ ] GitHub Release published
- [ ] Release notes published
- [ ] Container image pushed to registry
- [ ] Sign-off document archived

## Post-Release

- [ ] Announce release on communication channels
- [ ] Update deployment to new version
- [ ] Monitor SLOs for 72 hours post-release
- [ ] Schedule post-release retrospective
