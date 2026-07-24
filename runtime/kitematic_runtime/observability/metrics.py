"""Runtime metrics collection — counters, histograms, and gauges.

Provides lightweight in-memory metrics for monitoring runtime behavior.
Metrics are thread-safe for single-threaded use.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


class MetricsRegistry:
    """In-memory metrics registry with counters and histograms.

    Tracks:
      - Counters: cumulative totals (e.g. execution count)
      - Histograms: value distributions (e.g. latency in ms)
      - Gauges: point-in-time values (e.g. active executions)

    Metrics are name-spaced for organizational clarity.
    """

    def __init__(self, otel_meter: Any | None = None) -> None:
        self._counters: dict[str, int] = defaultdict(int)
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._gauges: dict[str, Any] = {}
        self._otel_meter = otel_meter
        self._otel_counters: dict[str, Any] = {}
        self._otel_histograms: dict[str, Any] = {}

    def _otel_counter(self, metric: str) -> Any | None:
        if self._otel_meter is None:
            return None
        if metric not in self._otel_counters:
            self._otel_counters[metric] = self._otel_meter.create_counter(
                metric.replace(".", "_"),
                description=f"Counter for {metric}",
            )
        return self._otel_counters[metric]

    def _otel_histogram(self, metric: str) -> Any | None:
        if self._otel_meter is None:
            return None
        if metric not in self._otel_histograms:
            self._otel_histograms[metric] = self._otel_meter.create_histogram(
                metric.replace(".", "_"),
                description=f"Histogram for {metric}",
            )
        return self._otel_histograms[metric]

    # ── Counters ────────────────────────────────────────────────────

    def increment(self, metric: str, value: int = 1) -> None:
        """Increment a counter metric."""
        self._counters[metric] += value
        otel = self._otel_counter(metric)
        if otel is not None:
            otel.add(value)

    def get_counter(self, metric: str) -> int:
        """Get current counter value."""
        return self._counters.get(metric, 0)

    # ── Histograms ──────────────────────────────────────────────────

    def record(self, metric: str, value: float) -> None:
        """Record a value in a histogram."""
        self._histograms[metric].append(value)
        otel = self._otel_histogram(metric)
        if otel is not None:
            otel.record(value)

    def get_histogram(self, metric: str) -> list[float]:
        """Get all recorded values for a histogram."""
        return list(self._histograms.get(metric, []))

    def get_histogram_summary(self, metric: str) -> dict[str, float]:
        """Get summary stats for a histogram (count, min, max, avg, p50, p99)."""
        values = self._histograms.get(metric, [])
        if not values:
            return {"count": 0, "min": 0, "max": 0, "avg": 0, "p50": 0, "p99": 0}

        sorted_vals = sorted(values)
        count = len(sorted_vals)
        total = sum(sorted_vals)

        return {
            "count": count,
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
            "avg": round(total / count, 2),
            "p50": sorted_vals[int(count * 0.50)],
            "p99": sorted_vals[int(count * 0.99)],
        }

    # ── Gauges ───────────────────────────────────────────────────────

    def set_gauge(self, metric: str, value: Any) -> None:
        """Set a gauge to a specific value."""
        self._gauges[metric] = value

    def get_gauge(self, metric: str) -> Any:
        """Get current gauge value."""
        return self._gauges.get(metric)

    def increment_gauge(self, metric: str, delta: int = 1) -> None:
        """Atomically increment a gauge."""
        current = self._gauges.get(metric, 0)
        self._gauges[metric] = current + delta

    # ── Snapshot ─────────────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        """Return a complete snapshot of all metrics.

        Useful for periodic reporting or debug endpoints.
        """
        hist_summaries: dict[str, dict[str, float]] = {}
        for name in self._histograms:
            hist_summaries[name] = self.get_histogram_summary(name)

        return {
            "counters": dict(self._counters),
            "histograms": hist_summaries,
            "gauges": dict(self._gauges),
        }
