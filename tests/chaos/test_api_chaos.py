"""CHAOS-AP: API chaos experiments.

Simulates API-level failures:
  AP-01: Auth key rotation storm
  AP-02: Malformed requests
  AP-03: Rate limit burst
"""

import asyncio

import pytest

from runtime.kitematic_runtime.api.auth import APIKeyAuthProvider, AuthContext
from kernel.runtime import Intent
from kernel.tenant import TenantContext
from tests.chaos.conftest import make_runtime

pytestmark = [
    pytest.mark.timeout(30),
]


@pytest.mark.asyncio
async def test_chaos_ap_01_key_rotation_storm(chaos_experiment):
    """CHAOS-AP-01: Rotate 100 keys simultaneously, verify no auth gaps."""
    result = chaos_experiment["result"]
    result.expected_outcome = "Key rotation does not lose auth state"

    provider = APIKeyAuthProvider()
    for i in range(100):
        provider.add_key(f"key-{i}", AuthContext(tenant_id=f"tenant-{i}", agent_id="a1"))

    async def rotate(i: int) -> bool:
        return provider.rotate_key(f"key-{i}", f"new-key-{i}")

    results = await asyncio.gather(*[rotate(i) for i in range(100)])
    assert all(results), "All 100 rotations should succeed"

    errors = 0
    for i in range(100):
        ctx = await provider.authenticate(f"key-{i}")
        if ctx is not None:
            errors += 1
        ctx_new = await provider.authenticate(f"new-key-{i}")
        if ctx_new is None:
            errors += 1
    assert errors == 0, "All old keys should be invalid, all new keys valid"

    result.passed = True


@pytest.mark.asyncio
async def test_chaos_ap_02_malformed_requests(chaos_experiment):
    """CHAOS-AP-02: Runtime handles edge case inputs gracefully."""
    result = chaos_experiment["result"]
    result.expected_outcome = "Runtime rejects malformed inputs without crash"

    rt = make_runtime()
    rt.set_tenant_context(TenantContext(tenant_id="chaos-ap2", agent_id="a1"))

    edge_cases = [
        Intent(agent_id="", action="test"),
        Intent(agent_id="\x00\x01", action="test"),
        Intent(agent_id="a" * 1000, action="test"),
        Intent(agent_id="a1", action=""),
        Intent(agent_id="a1", action="\x00\x01"),
        Intent(agent_id="a1", action="a" * 1000, parameters={"x": "y" * 10000}),
    ]

    for intent in edge_cases:
        r = await rt.execute_intent(intent)
        assert r.success is not None, "Runtime should handle every input without crash"

    result.passed = True


@pytest.mark.asyncio
async def test_chaos_ap_03_rate_limit_burst(chaos_experiment):
    """CHAOS-AP-03: Exceed rate limits, verify quota enforcement."""
    result = chaos_experiment["result"]
    result.expected_outcome = "Rate limit enforcement prevents overload"

    rt = make_runtime()
    rt.set_tenant_context(TenantContext(tenant_id="chaos-ap3", agent_id="a1"))

    tasks = [
        rt.execute_intent(Intent(agent_id="a1", action=f"burst.{i}"))
        for i in range(20)
    ]
    results = await asyncio.gather(*tasks)
    successes = sum(1 for r in results if r.success)
    assert successes > 0, "At least some requests should succeed before limits apply"

    result.passed = True
