"""OpenTelemetry provider — configures SDK singletons for the runtime.

Provides zero-config defaults (no-op when OTel is not configured)
and auto-configuration when standard OTel environment variables
(OTEL_SERVICE_NAME, OTEL_EXPORTER_OTLP_ENDPOINT, etc.) are present.

Usage:
    from kernel.observability.opentelemetry import get_tracer_provider

    tracer = get_tracer_provider().get_tracer("kitematic.runtime")
    with tracer.start_as_current_span("execution") as span:
        span.set_attribute("execution_id", "123")
"""

from __future__ import annotations

import os
from contextlib import suppress
from typing import Any

_HAS_OTEL = False
_tracer_provider: Any = None
_meter_provider: Any = None
_logger_provider: Any = None

try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    _HAS_OTEL = True
except ImportError:
    _HAS_OTEL = False


def is_enabled() -> bool:
    has_svc = os.environ.get("OTEL_SERVICE_NAME")
    has_otlp = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    return bool(_HAS_OTEL and (has_svc or has_otlp))


def get_tracer_provider() -> Any:
    global _tracer_provider
    if _tracer_provider is None and is_enabled():
        resource = Resource.create({
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "kitematic"),
        })
        _tracer_provider = SDKTracerProvider(resource=resource)
        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        if endpoint:
            exporter = OTLPSpanExporter(endpoint=endpoint)
            _tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
    if _tracer_provider is None:
        from opentelemetry import trace as _trace
        _tracer_provider = _trace.get_tracer_provider()
    return _tracer_provider


def get_tracer(name: str = "kitematic.runtime") -> Any:
    return get_tracer_provider().get_tracer(name)


def get_meter_provider() -> Any:
    global _meter_provider
    if _meter_provider is None:
        try:
            from opentelemetry import metrics
            _meter_provider = metrics.get_meter_provider()
        except ImportError:
            _meter_provider = type(
                "NoopMeterProvider",
                (),
                {"get_meter": lambda self, n, v=None: type("NoopMeter", (), {})()},
            )()
    return _meter_provider


def get_meter(name: str = "kitematic.runtime") -> Any:
    return get_meter_provider().get_meter(name)


def get_logger_provider() -> Any:
    global _logger_provider
    if _logger_provider is None:
        try:
            from opentelemetry._logs import get_logger_provider as _get_lp
            _logger_provider = _get_lp()
        except ImportError:
            _logger_provider = type(
                "NoopLoggerProvider",
                (),
                {
                    "get_logger": lambda self, n, v=None: type(
                        "NoopLogger", (), {"emit": lambda self, r: None}
                    )()
                },
            )()
    return _logger_provider


def get_logger(name: str = "kitematic.runtime") -> Any:
    return get_logger_provider().get_logger(name)


def shutdown() -> None:
    for provider in (_tracer_provider, _meter_provider, _logger_provider):
        if provider is not None:
            with suppress(Exception):
                provider.shutdown()
