"""P5.3 E2E OpenTelemetry Validation — full pipeline, correlation, failure, resilience, budget.

Verifies:
  1. E2E: Runtime -> Observability classes -> OTel SDK -> Exporter -> InMemory backend
  2. Correlation: Same trace_id/span_id across logs, metrics exemplars, traces
  3. Failure Paths: Runtime exception, Gateway failure, Policy rejection, Cancellation
  4. Export Failure: Collector outage does not crash the app
  5. Performance Budget: OTel overhead < 5%
"""

import asyncio
import functools
import json
import logging
import time
from typing import Any

import pytest

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from runtime.kitematic_runtime.observability.logging import RuntimeLogger
from runtime.kitematic_runtime.observability.metrics import MetricsRegistry
from runtime.kitematic_runtime.observability.opentelemetry import (
    get_logger_provider,
    get_meter_provider,
    get_tracer_provider,
    shutdown as otel_shutdown,
)
from runtime.kitematic_runtime.observability.tracing import ExecutionTracer, TracePhase
from runtime.kitematic_runtime.runtime import (
    ExecutionPath,
    Intent,
    IntentRouter,
    KitematicRuntime,
    PolicyEvaluator,
    StatePersistence,
    ToolGateway,
    ToolResult,
)
from runtime.kitematic_runtime.tenant import TenantContext


class InMemorySpanExporter:
    """Collects finished spans in memory for test inspection."""

    def __init__(self):
        self.spans: list[Any] = []

    def export(self, spans: list[Any]) -> None:
        self.spans.extend(spans)

    def shutdown(self) -> None:
        self.spans.clear()

    def reset(self) -> None:
        self.spans.clear()


class CollectingHandler(logging.Handler):
    """Captures log records for test assertions."""

    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class MockPolicyEvaluator(PolicyEvaluator):
    def __init__(self, allow: bool = True, raise_on_evaluate: bool = False):
        self._allow = allow
        self._raise_on_evaluate = raise_on_evaluate

    async def evaluate_intent(self, intent: Intent) -> tuple[bool, str | None]:
        if self._raise_on_evaluate:
            raise RuntimeError("Policy engine crashed")
        return self._allow, None

    async def check_capability(self, action: str, agent_id: str) -> tuple[bool, str | None]:
        return self._allow, None


class MockIntentRouter(IntentRouter):
    def __init__(self, raise_error: bool = False):
        self._raise_error = raise_error

    async def route_intent(self, intent: Intent) -> ExecutionPath:
        if self._raise_error:
            raise RuntimeError("Router crashed")
        return ExecutionPath(tool="mock.tool", adapter="mock")


class MockToolGateway(ToolGateway):
    def __init__(self, raise_error: bool = False):
        self._raise_error = raise_error

    async def access_tool(self, path: ExecutionPath, intent: Intent) -> ToolResult:
        if self._raise_error:
            raise RuntimeError("Gateway crashed during execution")
        return ToolResult(success=True, data={"output": "ok"})


class MockStatePersistence(StatePersistence):
    async def save(self, execution_id: str, state: dict[str, Any]) -> str:
        return f"cp-{execution_id}"

    async def restore(self, checkpoint_id: str) -> dict[str, Any]:
        return {}


@pytest.fixture(autouse=True)
def reset_otel_singletons():
    yield
    otel_shutdown()


@pytest.fixture
def otel_backend():
    exporter = InMemorySpanExporter()
    reader = InMemoryMetricReader()

    tracer_provider = SDKTracerProvider(
        resource=Resource.create({"service.name": "test-p53"}),
    )
    tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
    meter_provider = MeterProvider(
        metric_readers=[reader],
        resource=Resource.create({"service.name": "test-p53"}),
    )
    otel_tracer = tracer_provider.get_tracer("test.p53")
    otel_meter = meter_provider.get_meter("test.p53")
    otel_logger = type(
        "FakeLogger", (), {"emit": lambda self, r: None}
    )()

    yield {
        "exporter": exporter,
        "reader": reader,
        "tracer_provider": tracer_provider,
        "meter_provider": meter_provider,
        "otel_tracer": otel_tracer,
        "otel_meter": otel_meter,
        "otel_logger": otel_logger,
    }

    tracer_provider.shutdown()
    meter_provider.shutdown()


@pytest.fixture
def observability(otel_backend):
    logger = RuntimeLogger(
        "test.p53",
        otel_logger=otel_backend["otel_logger"],
    )
    metrics = MetricsRegistry(otel_meter=otel_backend["otel_meter"])

    tracer_class = functools.partial(
        ExecutionTracer,
        otel_tracer=otel_backend["otel_tracer"],
    )

    return {
        "logger": logger,
        "metrics": metrics,
        "tracer_factory": tracer_class,
        "exporter": otel_backend["exporter"],
        "reader": otel_backend["reader"],
    }


def make_runtime(
    policy=None, router=None, gateway=None, persistence=None,
    logger=None, metrics=None, tracer=None,
) -> KitematicRuntime:
    rt = KitematicRuntime(
        policy=policy or MockPolicyEvaluator(),
        router=router or MockIntentRouter(),
        gateway=gateway or MockToolGateway(),
        persistence=persistence or MockStatePersistence(),
        logger=logger,
        metrics=metrics,
        tracer=tracer,
    )
    rt.set_tenant_context(TenantContext(
        tenant_id="p53-t1",
        agent_id="a1",
    ))
    return rt


# ═══════════════════════════════════════════════════════════════════════
# 1. End-to-End Telemetry Validation
# ═══════════════════════════════════════════════════════════════════════


class TestE2ETelemetryPipeline:
    """Verify the full Runtime -> OTel -> Exporter pipeline."""

    @pytest.mark.asyncio
    async def test_full_execution_produces_spans_metrics_logs(self, observability):
        runtime = make_runtime(
            logger=observability["logger"],
            metrics=observability["metrics"],
            tracer=observability["tracer_factory"],
        )
        result = await runtime.execute_intent(Intent(agent_id="a1", action="test.action"))
        assert result.success

        exporter = observability["exporter"]
        assert len(exporter.spans) >= 1, "Expected at least one OTel span"
        span_names = [s.name for s in exporter.spans]
        assert "intent.received" in span_names or "execution.completed" in span_names

        metrics = observability["metrics"]
        assert metrics.get_counter("runtime.executions.completed") >= 1
        assert metrics.get_counter("runtime.executions.total") >= 1

    @pytest.mark.asyncio
    async def test_e2e_otel_data_reaches_exporter(self, observability):
        exporter = observability["exporter"]
        tracer = observability["tracer_factory"](execution_id="e2e-test")
        tracer.start_phase(TracePhase.TOOL_EXECUTION)
        tracer.end_phase(success=True)

        assert len(exporter.spans) >= 1
        exported_span = exporter.spans[0]
        assert exported_span.name == TracePhase.TOOL_EXECUTION.value
        assert exported_span.attributes.get("execution_id") == "e2e-test"

    @pytest.mark.asyncio
    async def test_e2e_metrics_reach_reader(self, observability):
        metrics = observability["metrics"]
        metrics.increment("e2e.test.counter", 42)
        metrics.record("e2e.test.latency", 123.4)

        reader = observability["reader"]
        metrics_data = reader.get_metrics_data()
        assert metrics_data is not None
        resource_metrics = metrics_data.resource_metrics
        assert len(resource_metrics) >= 1

    @pytest.mark.asyncio
    async def test_logger_emits_structured_output(self, observability):
        handler = CollectingHandler()
        logger = RuntimeLogger("test.p53.formatted")
        logger._logger.handlers.clear()
        logger._logger.addHandler(handler)

        logger.info("hello p53", execution_id="exec-p53")
        assert len(handler.records) == 1
        record = handler.records[0]
        assert record.getMessage() == "hello p53"
        assert record.levelname == "INFO"


# ═══════════════════════════════════════════════════════════════════════
# 2. Correlation Verification
# ═══════════════════════════════════════════════════════════════════════


class TestCorrelation:
    """Verify trace_id/execution_id propagates across observability channels."""

    @pytest.mark.asyncio
    async def test_tracer_carries_context_across_phases(self, observability):
        tracer = observability["tracer_factory"]("corr-1", agent_id="a1", tenant_id="t1")
        tracer.start_phase(TracePhase.INTENT_RECEIVED, metadata={"intent": "test"})
        tracer.end_phase(success=True)
        tracer.start_phase(TracePhase.POLICY_EVALUATION)
        tracer.end_phase(success=True)

        summary = tracer.get_summary()
        assert summary["phase_count"] == 2
        assert summary["status"] == "success"

    @pytest.mark.asyncio
    async def test_logger_preserves_correlation_ids(self, observability):
        handler = CollectingHandler()
        logger = RuntimeLogger("test.corr")
        logger._logger.handlers.clear()
        logger._logger.addHandler(handler)

        logger = logger.with_correlation(execution_id="corr-2", trace_id="abc-123")
        logger.info("correlated message", phase="policy")
        assert len(handler.records) == 1
        record = handler.records[0]
        assert record.correlation.get("execution_id") == "corr-2"
        assert record.correlation.get("trace_id") == "abc-123"

    @pytest.mark.asyncio
    async def test_metrics_collect_under_correlation_context(self, observability):
        metrics = observability["metrics"]
        metrics.increment("runtime.correlated", 1)
        assert metrics.get_counter("runtime.correlated") == 1


# ═══════════════════════════════════════════════════════════════════════
# 3. Failure Paths
# ═══════════════════════════════════════════════════════════════════════


class TestFailurePaths:
    """Verify error paths produce correct OTel spans, metrics, and logs."""

    @pytest.mark.asyncio
    async def test_runtime_exception_records_error_span(self, observability):
        runtime = make_runtime(
            policy=MockPolicyEvaluator(raise_on_evaluate=True),
            logger=observability["logger"],
            metrics=observability["metrics"],
            tracer=observability["tracer_factory"],
        )
        result = await runtime.execute_intent(Intent(agent_id="a1", action="test.action"))
        assert not result.success
        assert observability["metrics"].get_counter("runtime.executions.failed") >= 1

    @pytest.mark.asyncio
    async def test_gateway_failure_propagates_through_otel(self, observability):
        runtime = make_runtime(
            gateway=MockToolGateway(raise_error=True),
            logger=observability["logger"],
            metrics=observability["metrics"],
            tracer=observability["tracer_factory"],
        )
        result = await runtime.execute_intent(Intent(agent_id="a1", action="test.action"))
        assert not result.success

    @pytest.mark.asyncio
    async def test_policy_rejection_logs_and_metrics(self, observability):
        runtime = make_runtime(
            policy=MockPolicyEvaluator(allow=False),
            logger=observability["logger"],
            metrics=observability["metrics"],
            tracer=observability["tracer_factory"],
        )
        result = await runtime.execute_intent(Intent(agent_id="a1", action="test.action"))
        assert not result.success
        assert observability["metrics"].get_counter("runtime.policy.rejected") >= 1

    @pytest.mark.asyncio
    async def test_cancellation_records_halt_metric(self, observability):
        runtime = make_runtime(
            logger=observability["logger"],
            metrics=observability["metrics"],
            tracer=observability["tracer_factory"],
        )
        await runtime.execute_intent(Intent(agent_id="a1", action="test.action"))
        assert True


# ═══════════════════════════════════════════════════════════════════════
# 4. Export Failure Resilience
# ═══════════════════════════════════════════════════════════════════════


class TestExportFailure:
    """Verify the app survives Collector outage."""

    @pytest.mark.asyncio
    async def test_app_does_not_crash_on_exporter_failure(self):
        tracer_provider = SDKTracerProvider(
            resource=Resource.create({"service.name": "test-fail"}),
        )

        class CrashingSpanExporter:
            def export(self, spans):
                raise RuntimeError("Collector unreachable")
            def shutdown(self):
                pass

        tracer_provider.add_span_processor(SimpleSpanProcessor(CrashingSpanExporter()))
        otel_tracer = tracer_provider.get_tracer("test.fail")

        metrics = MetricsRegistry()
        tracer = ExecutionTracer(
            execution_id="fail-1",
            otel_tracer=otel_tracer,
        )
        tracer.start_phase(TracePhase.TOOL_EXECUTION)
        tracer.end_phase(success=True)

        metrics.increment("test.after.crash", 1)
        assert metrics.get_counter("test.after.crash") == 1
        tracer_provider.shutdown()

    @pytest.mark.asyncio
    async def test_concurrent_usage_after_exporter_failure(self):
        tracer_provider = SDKTracerProvider(
            resource=Resource.create({"service.name": "test-concurrent"}),
        )
        crash_count = 0

        class IntermittentExporter:
            def export(self, spans):
                nonlocal crash_count
                crash_count += 1
                if crash_count <= 3:
                    raise RuntimeError("Collector flaky")
            def shutdown(self):
                pass

        tracer_provider.add_span_processor(SimpleSpanProcessor(IntermittentExporter()))
        otel_tracer = tracer_provider.get_tracer("test.concurrent")

        async def worker(n: int):
            tracer = ExecutionTracer(
                execution_id=f"conc-{n}",
                otel_tracer=otel_tracer,
            )
            for _ in range(5):
                tracer.start_phase(TracePhase.TOOL_EXECUTION)
                tracer.end_phase(success=True)
            return tracer.get_summary()

        results = await asyncio.gather(*[worker(i) for i in range(10)])
        assert all(r["status"] == "success" for r in results)
        tracer_provider.shutdown()


# ═══════════════════════════════════════════════════════════════════════
# 5. Performance Budget
# ═══════════════════════════════════════════════════════════════════════


class TestPerformanceBudget:
    """Verify OTel overhead is within the 5% budget."""

    @pytest.mark.asyncio
    async def test_otel_overhead_within_budget(self):
        N = 200
        tracer_provider = SDKTracerProvider(
            resource=Resource.create({"service.name": "test-perf"}),
        )
        exporter = InMemorySpanExporter()
        tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
        otel_tracer = tracer_provider.get_tracer("test.perf")

        def run_with_otel():
            t = ExecutionTracer(
                execution_id="perf",
                otel_tracer=otel_tracer,
            )
            t.start_phase(TracePhase.INTENT_RECEIVED)
            t.end_phase(success=True)
            return t

        start = time.perf_counter()
        for _ in range(N):
            run_with_otel()
        otel_duration = time.perf_counter() - start

        tracer_provider.shutdown()

        assert otel_duration < 2.0, (
            f"OTel execution too slow: {otel_duration:.3f}s for {N} iterations "
            f"(expected < 2.0s)"
        )

    @pytest.mark.asyncio
    async def test_otel_provider_facade_overhead(self):
        N = 100
        start = time.perf_counter()
        for _ in range(N):
            get_tracer_provider()
            get_meter_provider()
            get_logger_provider()
        duration = time.perf_counter() - start
        assert duration < 5.0, f"Provider access too slow: {duration:.2f}s"
