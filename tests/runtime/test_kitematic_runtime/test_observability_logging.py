"""Tests for structured JSON logging."""

import io
import json

from runtime.kitematic_runtime.observability.logging import JSONLogFormatter, RuntimeLogger


class TestRuntimeLogger:
    """Tests for RuntimeLogger."""

    def test_info_logs_message(self):
        log = RuntimeLogger("test.logger")
        # Capture output
        captured = io.StringIO()
        handler = log._logger.handlers[0]
        old_stream = handler.stream
        handler.stream = captured
        try:
            log.info("Hello world")
            # Flush
            handler.flush()
            output = captured.getvalue()
            data = json.loads(output.strip())
            assert data["message"] == "Hello world"
            assert data["level"] == "INFO"
            assert data["logger"] == "test.logger"
            assert "timestamp" in data
        finally:
            handler.stream = old_stream

    def test_log_with_correlation_id(self):
        log = RuntimeLogger("test.correlation")
        captured = io.StringIO()
        handler = log._logger.handlers[0]
        old_stream = handler.stream
        handler.stream = captured
        try:
            log.info("Started", correlation={"execution_id": "exec-123", "tenant_id": "t1"})
            handler.flush()
            data = json.loads(captured.getvalue().strip())
            assert data["execution_id"] == "exec-123"
            assert data["tenant_id"] == "t1"
        finally:
            handler.stream = old_stream

    def test_log_with_extra_metrics(self):
        log = RuntimeLogger("test.metrics")
        captured = io.StringIO()
        handler = log._logger.handlers[0]
        old_stream = handler.stream
        handler.stream = captured
        try:
            log.info("Executed", duration_ms=142.5, status="COMPLETED")
            handler.flush()
            data = json.loads(captured.getvalue().strip())
            assert data["metrics"]["duration_ms"] == 142.5
            assert data["metrics"]["status"] == "COMPLETED"
        finally:
            handler.stream = old_stream

    def test_error_logs_level(self):
        log = RuntimeLogger("test.error")
        captured = io.StringIO()
        handler = log._logger.handlers[0]
        old_stream = handler.stream
        handler.stream = captured
        try:
            log.error("Something broke")
            handler.flush()
            data = json.loads(captured.getvalue().strip())
            assert data["level"] == "ERROR"
        finally:
            handler.stream = old_stream

    def test_warn_logs_level(self):
        log = RuntimeLogger("test.warn")
        captured = io.StringIO()
        handler = log._logger.handlers[0]
        old_stream = handler.stream
        handler.stream = captured
        try:
            log.warn("Something suspicious")
            handler.flush()
            data = json.loads(captured.getvalue().strip())
            assert data["level"] == "WARNING"
        finally:
            handler.stream = old_stream

    def test_debug_logs_level(self):
        log = RuntimeLogger("test.debug")
        captured = io.StringIO()
        handler = log._logger.handlers[0]
        old_stream = handler.stream
        handler.stream = captured
        try:
            log.debug("Detail info")
            handler.flush()
            data = json.loads(captured.getvalue().strip())
            assert data["level"] == "DEBUG"
        finally:
            handler.stream = old_stream


class TestRuntimeLoggerCorrelation:
    """Tests for correlation ID propagation."""

    def test_with_correlation_returns_new_logger(self):
        log = RuntimeLogger("test.base")
        child = log.with_correlation(execution_id="exec-001")
        assert child is not log

    def test_with_correlation_preserves_base(self):
        log = RuntimeLogger("test.preserve")
        child = log.with_correlation(execution_id="exec-001")

        captured = io.StringIO()
        handler = log._logger.handlers[0]
        old_stream = handler.stream
        handler.stream = captured
        try:
            child.info("Child message")
            handler.flush()
            data = json.loads(captured.getvalue().strip())
            assert data["execution_id"] == "exec-001"
        finally:
            handler.stream = old_stream


class TestJSONLogFormatter:
    """Tests for the JSON formatter."""

    def test_format_includes_timestamp(self):
        formatter = JSONLogFormatter()
        import logging
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert "timestamp" in data

    def test_format_omits_extra_when_not_set(self):
        formatter = JSONLogFormatter()
        import logging
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert "exception" not in data
