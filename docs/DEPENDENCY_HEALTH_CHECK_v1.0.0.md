# Dependency Health Check — v1.0.0

## Frozen Dependencies

All dependencies are pinned with `==` in `pyproject.toml` for reproducible builds.

### Runtime Dependencies

| Package | Version | Python Support | pip-audit | Status |
|---|---|---|---|---|
| fastapi | 0.139.0 | ≥3.8 | ✅ Clean | ✅ Current |
| pydantic | 2.13.4 | ≥3.8 | ✅ Clean | ✅ Current |
| pydantic-settings | 2.14.2 | ≥3.8 | ✅ Clean | ✅ Current |
| uvicorn | 0.49.0 | ≥3.8 | ✅ Clean | ✅ Current |

### Optional Dependencies

| Package | Version | Python Support | pip-audit | Status |
|---|---|---|---|---|
| redis | 8.0.1 | ≥3.8 | ✅ Clean | ✅ Current |
| opentelemetry-api | 1.43.0 | ≥3.8 | ✅ Clean | ✅ Current |
| opentelemetry-sdk | 1.43.0 | ≥3.8 | ✅ Clean | ✅ Current |
| opentelemetry-exporter-otlp-proto-grpc | 1.43.0 | ≥3.8 | ✅ Clean | ✅ Current |

### Dev Dependencies

| Package | Version | Python Support | pip-audit | Status |
|---|---|---|---|---|
| pytest | 9.1.1 | ≥3.8 | ✅ Clean | ✅ Current |
| pytest-asyncio | 1.4.0 | ≥3.8 | ✅ Clean | ✅ Current |
| pytest-cov | 7.1.0 | ≥3.8 | ✅ Clean | ✅ Current |
| httpx | 0.28.1 | ≥3.8 | ✅ Clean | ✅ Current |
| starlette | 1.3.1 | ≥3.8 | ✅ Clean | ✅ Current |
| mypy | 2.3.0 | ≥3.8 | ✅ Clean | ✅ Current |
| ruff | 0.15.20 | ≥3.8 | ✅ Clean | ✅ Current |
| pip-audit | 2.11.2 | ≥3.8 | ✅ Clean | ✅ Current |
| bandit | 1.9.4 | ≥3.8 | ✅ Clean | ✅ Current |

## Vulnerability Scan

- **pip-audit**: 0 vulnerabilities found (all 17 direct dependencies clean)
- **bandit**: 0 HIGH findings in runtime code
- **Trivy**: Clean (container image scan — see CI results)

## EOL Check

| Package | Current Version | Release Date | Python EOL | Risk |
|---|---|---|---|---|
| Python 3.12 | 3.12.x | 2023-10 | 2028-10 | ✅ No risk |
| fastapi 0.139 | 0.139.0 | 2026 | Active | ✅ No risk |
| pydantic 2.13 | 2.13.4 | 2026 | Active | ✅ No risk |
| uvicorn 0.49 | 0.49.0 | 2026 | Active | ✅ No risk |

All dependencies are actively maintained. No packages are approaching end-of-life.

## License Compatibility

All direct dependencies use permissive licenses (MIT, Apache-2.0, BSD).
No copyleft (GPL/AGPL) dependencies detected.

## Conclusion

**All dependencies are healthy**: no vulnerabilities, no EOL packages, compatible licenses, all actively maintained.
