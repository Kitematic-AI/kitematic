"""Multi-tenant quota management and rate limiting.

Provides:
  - TokenBucketRateLimiter: per-tenant rate limiting via token bucket
  - QuotaManager: pre-execution quota checks (concurrent, total, step)
  - QuotaExceededError / RateLimitError exceptions
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock


class RateLimitError(Exception):
    def __init__(self, tenant_id: str, retry_after: float = 0.0):
        self.tenant_id = tenant_id
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded for tenant {tenant_id!r}")


class QuotaExceededError(Exception):
    def __init__(self, tenant_id: str, limit_name: str, current: int, max_: int):
        self.tenant_id = tenant_id
        self.limit_name = limit_name
        self.current = current
        self.max = max_
        super().__init__(
            f"Quota {limit_name!r} exceeded for tenant {tenant_id!r}: "
            f"{current}/{max_}"
        )


@dataclass
class TokenBucket:
    tokens: float
    max_tokens: float
    refill_rate: float
    last_refill: float = field(default_factory=time.time)


class TokenBucketRateLimiter:
    """Per-tenant token bucket rate limiter.

    Each tenant has an independent token bucket.
    Tokens refill at refill_rate per second up to max_tokens.
    """

    def __init__(self, max_tokens: float = 100, refill_rate: float = 10.0):
        self._max_tokens = max_tokens
        self._refill_rate = refill_rate
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = Lock()

    def _get_bucket(self, tenant_id: str) -> TokenBucket:
        if tenant_id not in self._buckets:
            self._buckets[tenant_id] = TokenBucket(
                tokens=self._max_tokens,
                max_tokens=self._max_tokens,
                refill_rate=self._refill_rate,
            )
        return self._buckets[tenant_id]

    def _refill(self, bucket: TokenBucket) -> None:
        now = time.time()
        elapsed = now - bucket.last_refill
        bucket.tokens = min(bucket.max_tokens, bucket.tokens + elapsed * bucket.refill_rate)
        bucket.last_refill = now

    def consume(self, tenant_id: str, tokens: float = 1.0) -> bool:
        """Try to consume tokens. Returns True if allowed, False if rate limited."""
        with self._lock:
            bucket = self._get_bucket(tenant_id)
            self._refill(bucket)
            if bucket.tokens >= tokens:
                bucket.tokens -= tokens
                return True
            return False

    def retry_after(self, tenant_id: str) -> float:
        """Get seconds until the bucket refills enough for one token."""
        with self._lock:
            bucket = self._get_bucket(tenant_id)
            self._refill(bucket)
            deficit = 1.0 - bucket.tokens
            if deficit <= 0:
                return 0.0
            return deficit / bucket.refill_rate

    def reset(self, tenant_id: str) -> None:
        with self._lock:
            self._buckets.pop(tenant_id, None)


@dataclass
class TenantQuotaConfig:
    max_concurrent: int = 5
    max_total_per_minute: int = 60
    max_steps_per_execution: int = 10


class QuotaManager:
    """Pre-execution quota checks per tenant.

    Tracks concurrent executions, total execution rate, and step limits.
    """

    def __init__(self, rate_limiter: TokenBucketRateLimiter | None = None):
        self._rate_limiter = rate_limiter or TokenBucketRateLimiter()
        self._concurrent: dict[str, set[str]] = {}
        self._configs: dict[str, TenantQuotaConfig] = {}
        self._lock = Lock()

    def configure(self, tenant_id: str, config: TenantQuotaConfig) -> None:
        with self._lock:
            self._configs[tenant_id] = config

    def get_config(self, tenant_id: str) -> TenantQuotaConfig:
        with self._lock:
            return self._configs.get(tenant_id, TenantQuotaConfig())

    def check_concurrent(self, tenant_id: str) -> bool:
        """Check if tenant can start a new concurrent execution."""
        config = self.get_config(tenant_id)
        with self._lock:
            active = len(self._concurrent.get(tenant_id, set()))
            return active < config.max_concurrent

    def start_execution(self, tenant_id: str, execution_id: str) -> None:
        with self._lock:
            self._concurrent.setdefault(tenant_id, set()).add(execution_id)

    def end_execution(self, tenant_id: str, execution_id: str) -> None:
        with self._lock:
            execs = self._concurrent.get(tenant_id)
            if execs:
                execs.discard(execution_id)

    def concurrent_count(self, tenant_id: str) -> int:
        with self._lock:
            return len(self._concurrent.get(tenant_id, set()))

    def check_and_consume_rate(self, tenant_id: str) -> bool:
        """Check and consume a rate limit token. Returns True if allowed."""
        return self._rate_limiter.consume(tenant_id)

    def retry_after(self, tenant_id: str) -> float:
        return self._rate_limiter.retry_after(tenant_id)

    def cleanup(self, tenant_id: str) -> None:
        with self._lock:
            self._concurrent.pop(tenant_id, None)
        self._rate_limiter.reset(tenant_id)
