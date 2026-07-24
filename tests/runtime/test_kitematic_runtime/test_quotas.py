"""Tests for P4.3 — Multi-tenant quota management and rate limiting.

Covers:
  - TokenBucketRateLimiter
  - QuotaManager concurrent tracking
  - QuotaManager rate limiting
  - Quota integration in KitematicRuntime.execute_intent
  - Quota config in RuntimeSettings
  - Resource metrics
"""


import pytest

from runtime.kitematic_runtime.api.quotas import (
    QuotaExceededError,
    QuotaManager,
    RateLimitError,
    TenantQuotaConfig,
    TokenBucketRateLimiter,
)
from runtime.kitematic_runtime.config.settings import RuntimeSettings

# ── TokenBucketRateLimiter ───────────────────────────────────────


class TestTokenBucketRateLimiter:
    def test_allows_initial_burst(self):
        limiter = TokenBucketRateLimiter(max_tokens=10, refill_rate=10)
        for _ in range(10):
            assert limiter.consume("t1")

    def test_blocks_when_exhausted(self):
        limiter = TokenBucketRateLimiter(max_tokens=3, refill_rate=10)
        for _ in range(3):
            assert limiter.consume("t1")
        assert not limiter.consume("t1")

    def test_retry_after_returns_positive_when_exhausted(self):
        limiter = TokenBucketRateLimiter(max_tokens=1, refill_rate=1)
        limiter.consume("t1")
        retry = limiter.retry_after("t1")
        assert retry > 0

    def test_retry_after_returns_zero_when_available(self):
        limiter = TokenBucketRateLimiter(max_tokens=10, refill_rate=10)
        retry = limiter.retry_after("t1")
        assert retry == 0.0

    def test_independent_tenant_buckets(self):
        limiter = TokenBucketRateLimiter(max_tokens=1, refill_rate=10)
        assert limiter.consume("t1")
        assert not limiter.consume("t1")
        assert limiter.consume("t2")

    def test_reset_clears_bucket(self):
        limiter = TokenBucketRateLimiter(max_tokens=1, refill_rate=10)
        limiter.consume("t1")
        assert not limiter.consume("t1")
        limiter.reset("t1")
        assert limiter.consume("t1")


# ── QuotaManager ────────────────────────────────────────────────


class TestQuotaManager:
    def test_concurrent_check_allows_within_limit(self):
        mgr = QuotaManager()
        mgr.configure("t1", TenantQuotaConfig(max_concurrent=5))
        for i in range(4):
            mgr.start_execution("t1", f"exec-{i}")
        assert mgr.check_concurrent("t1")
        mgr.start_execution("t1", "exec-4")
        assert not mgr.check_concurrent("t1")

    def test_concurrent_count(self):
        mgr = QuotaManager()
        assert mgr.concurrent_count("t1") == 0
        mgr.start_execution("t1", "exec-1")
        assert mgr.concurrent_count("t1") == 1

    def test_end_execution_frees_slot(self):
        mgr = QuotaManager()
        mgr.configure("t1", TenantQuotaConfig(max_concurrent=1))
        mgr.start_execution("t1", "exec-1")
        assert not mgr.check_concurrent("t1")
        mgr.end_execution("t1", "exec-1")
        assert mgr.check_concurrent("t1")

    def test_rate_limiting(self):
        mgr = QuotaManager()
        assert mgr.check_and_consume_rate("t1")
        assert mgr.retry_after("t1") == 0.0
        rb = mgr._rate_limiter
        rb._buckets["t1"].tokens = 0
        assert not mgr.check_and_consume_rate("t1")

    def test_cleanup_removes_all_state(self):
        mgr = QuotaManager()
        mgr.start_execution("t1", "exec-1")
        mgr.cleanup("t1")
        assert mgr.concurrent_count("t1") == 0

    def test_default_config(self):
        mgr = QuotaManager()
        cfg = mgr.get_config("unknown")
        assert cfg.max_concurrent == 5
        assert cfg.max_total_per_minute == 60
        assert cfg.max_steps_per_execution == 10


# ── Quota Integration with Runtime ──────────────────────────────


class TestQuotaIntegration:
    """QuotaManager wired into KitematicRuntime.execute_intent."""

    @pytest.fixture
    def runtime(self):
        from tests.runtime.test_kitematic_runtime.test_lifecycle import make_runtime
        rt = make_runtime()
        qm = QuotaManager()
        rt._quota_manager = qm
        from runtime.kitematic_runtime.tenant import TenantContext
        rt.set_tenant_context(TenantContext(tenant_id="t1", agent_id="a1"))
        return rt, qm

    @pytest.mark.asyncio
    async def test_execute_intent_respects_concurrent_limit(self, runtime):
        rt, qm = runtime
        qm.configure("t1", TenantQuotaConfig(max_concurrent=1))
        qm.start_execution("t1", "blocking-exec")
        from runtime.kitematic_runtime.runtime import Intent
        result = await rt.execute_intent(Intent(agent_id="a1", action="test"))
        assert not result.success
        assert "concurrent" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_intent_releases_quota_on_success(self, runtime):
        rt, qm = runtime
        from runtime.kitematic_runtime.runtime import Intent
        result = await rt.execute_intent(Intent(agent_id="a1", action="test"))
        assert result.success
        assert qm.concurrent_count("t1") == 0

    @pytest.mark.asyncio
    async def test_execute_intent_releases_quota_on_failure(self, runtime):
        rt, qm = runtime
        qm.configure("t1", TenantQuotaConfig(max_concurrent=1))
        qm.start_execution("t1", "full-slot")
        from runtime.kitematic_runtime.runtime import Intent
        result = await rt.execute_intent(Intent(agent_id="a1", action="test"))
        assert not result.success
        assert qm.concurrent_count("t1") == 1

    @pytest.mark.asyncio
    async def test_execute_intent_rate_limited(self, runtime):
        rt, qm = runtime
        qm._rate_limiter._buckets["t1"] = qm._rate_limiter._get_bucket("t1")
        qm._rate_limiter._buckets["t1"].tokens = 0
        from runtime.kitematic_runtime.runtime import Intent
        result = await rt.execute_intent(Intent(agent_id="a1", action="test"))
        assert not result.success
        assert "rate limit" in result.error.lower()


# ── Quota Settings ──────────────────────────────────────────────


class TestQuotaSettings:
    def test_default_quota_values(self):
        settings = RuntimeSettings()
        assert settings.quota_max_concurrent == 5
        assert settings.quota_max_per_minute == 60
        assert settings.quota_max_steps == 10
        assert settings.quota_rate_limit_per_second == 10.0
        assert settings.quota_burst_size == 100

    def test_quota_env_prefix(self, monkeypatch):
        monkeypatch.setenv("KITEMATIC_QUOTA_MAX_CONCURRENT", "20")
        settings = RuntimeSettings()
        assert settings.quota_max_concurrent == 20

    def test_quota_zero_disables(self):
        settings = RuntimeSettings(quota_max_concurrent=0)
        assert settings.quota_max_concurrent == 0

    def test_quota_negative_not_allowed(self):
        with pytest.raises(Exception):
            RuntimeSettings(quota_max_concurrent=-1)

    def test_quota_burst_override(self, monkeypatch):
        monkeypatch.setenv("KITEMATIC_QUOTA_BURST_SIZE", "200")
        settings = RuntimeSettings()
        assert settings.quota_burst_size == 200

    def test_quota_rate_limit_env(self, monkeypatch):
        monkeypatch.setenv("KITEMATIC_QUOTA_RATE_LIMIT_PER_SECOND", "25.0")
        settings = RuntimeSettings()
        assert settings.quota_rate_limit_per_second == 25.0


class TestQuotaExceptions:
    def test_rate_limit_error_message(self):
        err = RateLimitError("t1", retry_after=2.5)
        assert "t1" in str(err)
        assert err.retry_after == 2.5

    def test_quota_exceeded_error_message(self):
        err = QuotaExceededError("t1", "max_concurrent", 5, 5)
        assert "t1" in str(err)
        assert "max_concurrent" in str(err)
        assert err.current == 5
        assert err.max == 5

    def test_rate_limit_error_no_retry_default(self):
        err = RateLimitError("t2")
        assert err.retry_after == 0.0
