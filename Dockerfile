# ── Stage 1: Install dependencies ──
FROM python:3.13-slim AS builder

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir build && \
    python -m build --wheel --no-isolation 2>/dev/null || true

# ── Stage 2: Runtime image ──
FROM python:3.13-slim

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages || true

COPY runtime/ ./runtime/
COPY pyproject.toml .

RUN pip install --no-cache-dir -e ".[redis,otel]" 2>/dev/null || \
    pip install --no-cache-dir -e "."

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

ENTRYPOINT ["kitematic-api"]
