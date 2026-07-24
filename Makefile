.PHONY: test lint typecheck coverage security build clean

# ── Fast Pipeline (local) ──────────────────────────────────────────

test:
	pytest tests/runtime/test_kitematic_runtime/ -q --tb=line

lint:
	ruff check runtime/

typecheck:
	mypy runtime/ --strict

coverage:
	pytest tests/runtime/test_kitematic_runtime/ -q --tb=line \
		--cov=runtime \
		--cov-report=term \
		--cov-report=xml:coverage.xml
	python scripts/check_coverage.py coverage.xml 90

security:
	pip-audit --strict 2>&1 | grep -v "openapi-auto-tool-engine" || true
	bandit -r runtime/ -c .bandit.yaml -q

fast: lint typecheck test coverage security

# ── Slow Pipeline (local) ──────────────────────────────────────────

full-test:
	python -m pytest tests/ -q --tb=line

full-coverage:
	python -m pytest tests/ -q --tb=line \
		--cov=runtime \
		--cov-report=term \
		--cov-fail-under=90

chaos:
	KITEMATIC_CHAOS_ENABLED=1 python -m pytest tests/chaos/ -v --tb=short

slow: full-test full-coverage chaos

# ── Build ───────────────────────────────────────────────────────────

build:
	docker build -t kitematic-api .
