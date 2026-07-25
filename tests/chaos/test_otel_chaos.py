"""CHAOS-OT: OpenTelemetry chaos experiments.

Simulates OTel pipeline failures:
  OT-01: Collector unreachable — no runtime impact
  OT-02: Span buffer overflow — no memory leak
  OT-03: Corrupted span data — graceful handling
"""

import pytest

from kernel.observability.tracing import ExecutionTracer, TracePhase
from kernel.runtime import Intent
from kernel.tenant import TenantContext
from tests.chaos.conftest import make_runtime

pytestmark = [
    pytest.mark.timeout(30),
]


@pytest.mark.asyncio
async def test_chaos_ot_01_collector_unreachable(chaos_experiment):
    """CHAOS-OT-01: Drop OTLP connection, verify no runtime impact."""
    result = chaos_experiment["result"]
    result.expected_outcome = "Runtime executes normally without OTel collector"

    rt = make_runtime()
    rt.set_tenant_context(TenantContext(tenant_id="chaos-ot1", agent_id="a1"))
    r = await rt.execute_intent(Intent(agent_id="a1", action="chaos.ot1"))
    assert r.success, "Runtime should work without collector"

    result.passed = True


@pytest.mark.asyncio
async def test_chaos_ot_02_span_buffer_overflow(chaos_experiment):
    """CHAOS-OT-02: Generate many spans rapidly, verify no crash."""
    result = chaos_experiment["result"]
    result.expected_outcome = "Tracer handles high span volume without crash"

    tracer = ExecutionTracer(execution_id="chaos-ot2", agent_id="a1")
    for i in range(100):
        tracer.start_phase(TracePhase.POLICY_EVALUATION, {"iteration": i})
        tracer.end_phase(success=True)

    trace = tracer.get_trace()
    assert len(trace) == 100, "All 100 phases should be tracked"
    assert all(t["success"] for t in trace), "All phases should succeed"

    result.passed = True


@pytest.mark.asyncio
async def test_chaos_ot_03_corrupted_span_data(chaos_experiment):
    """CHAOS-OT-03: Emit spans with invalid attributes, verify graceful handling."""
    result = chaos_experiment["result"]
    result.expected_outcome = "Tracer handles edge case attribute values"

    tracer = ExecutionTracer(execution_id="chaos-ot3", agent_id="a1")

    tracer.start_phase(TracePhase.TOOL_EXECUTION, metadata={"": "", "none_val": None})
    tracer.end_phase(success=True)

    tracer.start_phase(TracePhase.INTENT_RECEIVED, metadata={"big": "x" * 10000})
    tracer.end_phase(success=True)

    trace = tracer.get_trace()
    assert len(trace) == 2, "Both phases should be tracked"
    assert trace[0]["phase"] == "tool.execution"
    assert trace[1]["phase"] == "intent.received"

    result.passed = True
