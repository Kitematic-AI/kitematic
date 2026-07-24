"""Tests for runtime metrics collection."""


from runtime.kitematic_runtime.observability.metrics import MetricsRegistry


class TestMetricsRegistryCounters:
    """Tests for counter metrics."""

    def test_increment_default(self):
        reg = MetricsRegistry()
        reg.increment("execution_total")
        assert reg.get_counter("execution_total") == 1

    def test_increment_multiple(self):
        reg = MetricsRegistry()
        reg.increment("execution_total")
        reg.increment("execution_total")
        reg.increment("execution_total")
        assert reg.get_counter("execution_total") == 3

    def test_increment_custom_value(self):
        reg = MetricsRegistry()
        reg.increment("batch_count", 10)
        assert reg.get_counter("batch_count") == 10

    def test_counter_default_zero(self):
        reg = MetricsRegistry()
        assert reg.get_counter("nonexistent") == 0

    def test_multiple_counters(self):
        reg = MetricsRegistry()
        reg.increment("success")
        reg.increment("failure")
        reg.increment("success")
        assert reg.get_counter("success") == 2
        assert reg.get_counter("failure") == 1


class TestMetricsRegistryHistograms:
    """Tests for histogram metrics."""

    def test_record_values(self):
        reg = MetricsRegistry()
        reg.record("latency_ms", 100)
        reg.record("latency_ms", 200)
        values = reg.get_histogram("latency_ms")
        assert values == [100, 200]

    def test_histogram_summary(self):
        reg = MetricsRegistry()
        reg.record("latency_ms", 50)
        reg.record("latency_ms", 100)
        reg.record("latency_ms", 150)

        summary = reg.get_histogram_summary("latency_ms")
        assert summary["count"] == 3
        assert summary["min"] == 50
        assert summary["max"] == 150
        assert summary["avg"] == 100.0

    def test_histogram_summary_empty(self):
        reg = MetricsRegistry()
        summary = reg.get_histogram_summary("empty")
        assert summary["count"] == 0
        assert summary["min"] == 0
        assert summary["max"] == 0

    def test_histogram_percentiles(self):
        reg = MetricsRegistry()
        for i in range(1, 101):
            reg.record("pct", i)

        summary = reg.get_histogram_summary("pct")
        assert summary["count"] == 100
        assert summary["p50"] == 51  # sorted_vals[50] = 51 for [1..100]
        assert summary["p99"] == 100  # sorted_vals[99] = 100

    def test_empty_histogram(self):
        reg = MetricsRegistry()
        assert reg.get_histogram("nonexistent") == []


class TestMetricsRegistryGauges:
    """Tests for gauge metrics."""

    def test_set_and_get(self):
        reg = MetricsRegistry()
        reg.set_gauge("active_executions", 5)
        assert reg.get_gauge("active_executions") == 5

    def test_increment_gauge(self):
        reg = MetricsRegistry()
        reg.increment_gauge("active_executions")
        assert reg.get_gauge("active_executions") == 1

    def test_decrement_gauge(self):
        reg = MetricsRegistry()
        reg.increment_gauge("active_executions", 5)
        reg.increment_gauge("active_executions", -1)
        assert reg.get_gauge("active_executions") == 4

    def test_gauge_default_none(self):
        reg = MetricsRegistry()
        assert reg.get_gauge("nonexistent") is None


class TestMetricsRegistrySnapshot:
    """Tests for snapshot functionality."""

    def test_snapshot_returns_all_metrics(self):
        reg = MetricsRegistry()
        reg.increment("execution_total", 10)
        reg.record("latency_ms", 50)
        reg.set_gauge("active", 3)

        snap = reg.snapshot()

        assert snap["counters"]["execution_total"] == 10
        assert snap["histograms"]["latency_ms"]["count"] == 1
        assert snap["gauges"]["active"] == 3

    def test_snapshot_empty(self):
        reg = MetricsRegistry()
        snap = reg.snapshot()
        assert snap["counters"] == {}
        assert snap["histograms"] == {}
        assert snap["gauges"] == {}
