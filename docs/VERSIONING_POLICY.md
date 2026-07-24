# Versioning Policy

## Schema

Kitematic Runtime follows [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html):

```
MAJOR.MINOR.PATCH[-PRERELEASE[.ID]]
```

| Component | Meaning | When to Bump |
|---|---|---|
| MAJOR | Breaking API/ABI changes | Breaking change to public ABI |
| MINOR | New features, backward compatible | Feature release |
| PATCH | Bug fixes, backward compatible | Bug fix release |
| PRERELEASE | Release candidate | `rc.N` — before stable release |

## Release Cadence

| Phase | Frequency | Examples |
|---|---|---|
| Pre-release (0.x) | No fixed schedule | 0.1.0, 0.2.0 |
| Release Candidate | As needed per RC cycle | 1.0.0-rc.1, 1.0.0-rc.2 |
| Stable (1.x) | Quarterly MINOR, bi-weekly PATCH | 1.0.0, 1.1.0, 1.1.1 |
| LTS | Annual | 1.4.0 (LTS) — 2 years support |

## Stability Guarantees

### MAJOR version guarantees
- Public ABI contracts (`Intent`, `ExecutionResult`, `KitematicRuntime` methods) are stable within a MAJOR version
- Breaking changes require a MAJOR version bump

### MINOR version guarantees
- New features, no breaking changes
- Deprecation warnings added before removal (at least one MINOR version notice)

### PATCH version guarantees
- Bug fixes only, no new features
- Security fixes backported to the last two MINOR releases

## Release Candidate Rules

1. RC tags are pre-release identifiers: `v1.0.0-rc.1`
2. Each RC must pass all [RC validation gates](RELEASE_CHECKLIST.md)
3. RCs are not production releases — they are validation artifacts
4. The final stable release (`v1.0.0`) must pass all RC gates + review sign-off

## Branch Strategy

```
main          ─── latest development (feature-freeze during RC)
                  │
v1.0.0-rc.1   ─── release candidate tag
v1.0.0        ─── stable release tag
                  │
v1.0.x        ─── patch branch (critical fixes only)
v1.1.0        ─── next feature release
```
