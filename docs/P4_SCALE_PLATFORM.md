# P4 — Scale & Platform Engineering

## Architecture Decisions

| Area | Decision |
|------|----------|
| **Tenancy** | Multi-tenant from day one. Phase 1: in-process. Phase 2: multi-instance. |
| **Throughput** | ~1,000 exec/s target. |
| **Deployment** | Docker Compose (dev) + Kubernetes (production). |
| **Observability** | OpenTelemetry SDK, facade layer preserving existing RuntimeLogger/MetricsRegistry/ExecutionTracer. Phase 1: OTel SDK + OTLP export. Phase 2: Prometheus + dashboards. |
| **Event Backbone** | Redis Streams (upgrade from Pub/Sub, no new dependency). NATS/Kafka deferred. |

## Execution Plan (6 Steps)

### P4.1 — Observability: OpenTelemetry Facade

Replace internals of MetricsRegistry, ExecutionTracer, and RuntimeLogger with OpenTelemetry SDK calls.
Keep public API unchanged.

- `runtime/kitematic_runtime/observability/opentelemetry.py` — singleton TracerProvider, MeterProvider + OTLP exporter config
- RuntimeLogger → wraps OTel Logger
- MetricsRegistry → wraps OTel Meter
- ExecutionTracer → wraps OTel Tracer
- No test changes (facade preserves current interfaces)

### P4.2 — Event Infrastructure: Redis Streams

Replace Redis Pub/Sub with Redis Streams. Add consumer groups, replay, acknowledgment.

- `runtime/kitematic_runtime/events/redis_streams.py` — RedisStreamPublisher (XADD), StreamConsumer (XREADGROUP), consumer group management
- Consumer group per tenant (tenant-aware consumption)
- InMemoryEventPublisher stays (local dev, no Redis)
- Old RedisEventPublisher deprecated

### P4.3 — Multi-Tenant Resource Management

Add per-tenant quotas, rate limits, fair scheduling (in-process phase).

- `runtime/kitematic_runtime/api/quotas.py` — RateLimiter(token_bucket_per_tenant), QuotaManager
- runtime.execute_intent — check quota before accepting
- Rate limit middleware per tenant in API
- Metrics: resource.quota.exceeded, resource.rate_limit.hit

### P4.4 — Deployment: Docker + Kubernetes

Containerization + orchestration manifests.

- Dockerfile (multi-stage, distroless runtime image)
- docker-compose.yml (kitematic-api + Redis + OTel collector)
- deploy/k8s/ (deployment, service, ingress, configmap, secret, hpa)
- deploy/helm/kitematic/ — Helm chart

### P4.5 — Reliability Engineering

Chaos + load + recovery testing.

- tests/performance/test_load.py — 1,000 exec/s target
- tests/chaos/test_redis_failover.py, test_restart_recovery.py, test_event_loss.py
- Graceful degradation paths

### P4.6 — Distributed Runtime (Deferred)

Multi-instance: leader election (Redis SETNX/Redlock), distributed checkpoint ownership, execution ownership handoff.

## Results

| Step | Cumulative Tests |
|------|----------------:|
| P3 close | 551 |
| P4.1 OTel facade | 566 ✅ |
| P4.2 Redis Streams | 596 ✅ |
| P4.3 Multi-tenant quotas | 621 ✅ |
| P4.4 Docker + K8s | 632 ✅ |
| P4.5 Reliability | 644 ✅ |

## Status

| Step | Status |
|------|--------|
| P4.1 OTel facade | ✅ Complete |
| P4.2 Redis Streams | ✅ Complete |
| P4.3 Multi-tenant quotas | ✅ Complete |
| P4.4 Docker + K8s | ✅ Complete |
| P4.5 Reliability | ✅ Complete |
| P4.6 Distributed | ⏳ Deferred |

## What was built

### P4.1 — Observability: OpenTelemetry Facade
- `observability/opentelemetry.py` — OTel provider singleton (TracerProvider, MeterProvider, LoggerProvider)
- OTLP exporter via env vars (OTEL_SERVICE_NAME, OTEL_EXPORTER_OTLP_ENDPOINT)
- RuntimeLogger → delegates to OTel Logger when configured
- MetricsRegistry → counters/histograms via OTel Meter when configured
- ExecutionTracer → OTel spans per phase when configured
- Zero-config defaults: no-op when OTel not configured, all existing tests pass unchanged
- Tests: 15 (provider, counter, histogram, spans, error recording, multi-phase, logger delegation, shutdown)

### P4.2 — Event Infrastructure: Redis Streams
- `events/redis_streams.py` — RedisStreamPublisher implements EventPublisher protocol
- XADD for publishing with maxlen=10000, consumer groups per tenant, XREADGROUP for consumption
- Replay via XRANGE, acknowledgment via XACK, trim via XTRIM
- Local subscriber queues for same-process delivery (same pattern as InMemoryEventPublisher)
- Factory updated: supports `redis_streams` / `streams` backend aliases
- Old RedisEventPublisher (Pub/Sub) remains for backward compat
- Settings updated: accepts `redis_streams`, `redis_pubsub`, `streams`
- Tests: 27 (protocol, construction, local queues, mocked stream ops, factory routing)

### P4.3 — Multi-Tenant Resource Management
- `api/quotas.py` — TokenBucketRateLimiter (per-tenant, refill rate, burst), QuotaManager (concurrent tracking)
- RateLimitError, QuotaExceededError exceptions
- Quota check in KitematicRuntime.execute_intent: concurrent + rate limit gate
- Quota release on all execution paths (success + failure)
- RuntimeSettings: quota_max_concurrent, quota_max_per_minute, quota_max_steps, quota_rate_limit_per_second, quota_burst_size
- Metrics: resource.quota.exceeded, resource.rate_limit.hit
- Tests: 26 (rate limiter, quota manager, integration with runtime, settings)

### P4.4 — Deployment: Docker + Kubernetes
- Dockerfile (multi-stage, healthcheck, entrypoint)
- .dockerignore
- docker-compose.yml (kitematic-api + Redis + OTel collector [profile])
- deploy/k8s/configmap.yaml, deployment.yaml, service.yaml, hpa.yaml, secret.yaml, ingress.yaml
- deploy/helm/kitematic/ — Helm chart with values.yaml
- deploy/otel-collector.yml — local OTel collector config
- Tests: 11 (Dockerfile, docker-compose, K8s manifests, otel-collector, pyproject extras)

### P4.5 — Reliability Engineering
- tests/performance/test_load.py — 5 load tests (concurrent, burst rate limit, metrics under load, quota metrics, throughput)
- tests/chaos/test_recovery.py — 7 chaos tests (drain recovery, in-flight completion, Redis disconnect, stream replay, consumer group BUSYGROUP, metrics survival, concurrent drain+execution)
