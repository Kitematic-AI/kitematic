"""Structured JSON logging for runtime observability.

Produces JSON-formatted log lines with correlation IDs for
execution tracing across the runtime stack.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class JSONLogFormatter(logging.Formatter):
    """Format log records as JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if hasattr(record, "correlation") and record.correlation:
            entry.update(record.correlation)

        if record.exc_info and record.exc_info[0]:
            entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
            }

        if hasattr(record, "metrics") and record.metrics:
            entry["metrics"] = record.metrics

        return json.dumps(entry, sort_keys=True, default=str)


class RuntimeLogger:
    """Structured logger with correlation ID tracking.

    Usage:
        log = RuntimeLogger("runtime.execution")
        log.info("Execution started", execution_id="exec-123", tenant_id="t1")
    """

    def __init__(self, name: str = "kitematic.runtime", otel_logger: Any | None = None):
        self._logger = logging.getLogger(name)
        self._base_correlation: dict[str, Any] = {}
        self._otel_logger = otel_logger
        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(JSONLogFormatter())
            self._logger.addHandler(handler)
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False

    def _log(
        self,
        level: int,
        message: str,
        correlation: dict[str, Any] | None = None,
        **extra: Any,
    ) -> None:
        record = self._logger.makeRecord(
            name=self._logger.name,
            level=level,
            fn="",
            lno=0,
            msg=message,
            args=(),
            exc_info=None,
        )
        merged = {**self._base_correlation, **(correlation or {})}
        record.correlation = merged
        record.metrics = extra if extra else None
        self._logger.handle(record)
        if self._otel_logger is not None:
            self._otel_logger.emit(record)

    def info(self, message: str, **kwargs: Any) -> None:
        self._log(logging.INFO, message, **kwargs)

    def warn(self, message: str, **kwargs: Any) -> None:
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self._log(logging.ERROR, message, **kwargs)

    def debug(self, message: str, **kwargs: Any) -> None:
        self._log(logging.DEBUG, message, **kwargs)

    def with_correlation(self, **correlation: Any) -> RuntimeLogger:
        """Return a new logger with pre-set correlation IDs."""
        clone = RuntimeLogger(self._logger.name)
        clone._logger = self._logger
        clone._base_correlation = {**self._base_correlation, **correlation}
        return clone
