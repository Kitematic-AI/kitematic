"""Tests for the OpenTelemetry facade layer.

Verifies that RuntimeLogger, MetricsRegistry, and ExecutionTracer
correctly delegate to OTel backends when provided, and gracefully
handle the absence of OTel (default behavior, already tested in
the core test suite).
"""

from opentelemetry import trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.resources import Resource

from kernel.observability.logging import RuntimeLogger
from kernel.observability.metrics import MetricsRegistry
from kernel.observability.opentelemetry import get_tracer_provider, is_enabled
from kernel.observability.tracing import ExecutionTracer, TracePhase


class TestOTelProvider:
    def test_is_enabled_returns_false_by_default(self):
        assert is_enabled() is False

    def test_get_tracer_provider_returns_noop_when_disabled(self):
        provider = get_tracer_provider()
        tracer = provider.get_tracer("test")
        with tracer.start_as_current_span("test"):
            pass


class TestMetricsRegistryWithOTel:
    def setup_method(self):
        self.reader = InMemoryMetricReader()
        self.meter_provider = MeterProvider(
            metric_readers=[self.reader],
            resource=Resource.create({"service.name": "test"}),
        )
        self.meter = self.meter_provider.get_meter("test")

    def teardown_method(self):
        self.meter_provider.shutdown()

    def test_otel_counter_increments(self):
        registry = MetricsRegistry(otel_meter=self.meter)
        registry.increment("test.counter", 5)
        assert registry.get_counter("test.counter") == 5

    def test_otel_histogram_records(self):
        registry = MetricsRegistry(otel_meter=self.meter)
        registry.record("test.histogram", 42.0)
        vals = registry.get_histogram("test.histogram")
        assert 42.0 in vals

    def test_otel_snapshot_still_works(self):
        registry = MetricsRegistry(otel_meter=self.meter)
        registry.increment("test.counter", 3)
        snap = registry.snapshot()
        assert snap["counters"]["test.counter"] == 3


class TestExecutionTracerWithOTel:
    def test_otel_tracer_creates_spans(self):
        tracer_provider = trace.get_tracer_provider()
        otel_tracer = tracer_provider.get_tracer("test")
        tracer = ExecutionTracer(
            execution_id="exec-1",
            agent_id="a1",
            tenant_id="t1",
            otel_tracer=otel_tracer,
        )
        tracer.start_phase(TracePhase.POLICY_EVALUATION, metadata={"key": "val"})
        entry = tracer.end_phase(success=True)
        assert entry.phase == TracePhase.POLICY_EVALUATION
        assert entry.success
        trace_result = tracer.get_trace()
        assert len(trace_result) == 1

    def test_otel_tracer_records_error(self):
        tracer_provider = trace.get_tracer_provider()
        otel_tracer = tracer_provider.get_tracer("test")
        tracer = ExecutionTracer(
            execution_id="exec-2",
            otel_tracer=otel_tracer,
        )
        tracer.start_phase(TracePhase.TOOL_EXECUTION)
        entry = tracer.end_phase(success=False, error="timeout")
        assert entry.error == "timeout"
        assert not entry.success

    def test_otel_tracer_multiple_phases(self):
        tracer_provider = trace.get_tracer_provider()
        otel_tracer = tracer_provider.get_tracer("test")
        tracer = ExecutionTracer(
            execution_id="exec-3",
            otel_tracer=otel_tracer,
        )
        tracer.start_phase(TracePhase.INTENT_RECEIVED)
        p1 = tracer.end_phase(success=True)
        tracer.start_phase(TracePhase.POLICY_EVALUATION)
        p2 = tracer.end_phase(success=True)
        assert p1.phase == TracePhase.INTENT_RECEIVED
        assert p2.phase == TracePhase.POLICY_EVALUATION
        assert len(tracer.get_trace()) == 2

    def test_otel_tracer_auto_end_previous_phase(self):
        tracer_provider = trace.get_tracer_provider()
        otel_tracer = tracer_provider.get_tracer("test")
        tracer = ExecutionTracer(
            execution_id="exec-4",
            otel_tracer=otel_tracer,
        )
        tracer.start_phase(TracePhase.INTENT_RECEIVED)
        tracer.start_phase(TracePhase.POLICY_EVALUATION)
        assert tracer._current_phase == TracePhase.POLICY_EVALUATION


class TestRuntimeLoggerWithOTel:
    def test_otel_logger_accepts_otel_backend(self):
        otel_logger = type("FakeLogger", (), {"emit": lambda self, r: None})()
        logger = RuntimeLogger("test.otel", otel_logger=otel_logger)
        logger.info("hello from otel")

    def test_otel_logger_delegates_emit(self):
        emitted: list = []
        otel_logger = type("FakeLogger", (), {"emit": lambda self, r: emitted.append(r)})()
        logger = RuntimeLogger("test.otel.delegate", otel_logger=otel_logger)
        logger.error("test error", execution_id="e1")
        assert len(emitted) == 1


class TestOTelGetters:
    def test_get_tracer_provider_returns_singleton(self):
        p1 = get_tracer_provider()
        p2 = get_tracer_provider()
        assert p1 is p2

    def test_shutdown_noop_when_not_initialized(self):
        from kernel.observability.opentelemetry import shutdown
        shutdown()

    def test_get_meter_provider_returns_singleton(self):
        from kernel.observability.opentelemetry import get_meter_provider
        m1 = get_meter_provider()
        m2 = get_meter_provider()
        assert m1 is m2

    def test_get_logger_provider_returns_singleton(self):
        from kernel.observability.opentelemetry import get_logger_provider
        l1 = get_logger_provider()
        l2 = get_logger_provider()
        assert l1 is l2
