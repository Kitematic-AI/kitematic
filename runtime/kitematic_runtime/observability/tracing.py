"""Execution tracing — phase-level timing and result tracking for runtime executions.

Records every phase of the execution lifecycle:
  Intent → Policy → Routing → Gateway → Checkpoint → Completion

Each phase captures: start time, end time, duration, result, and error context.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

try:
    from opentelemetry.trace import Status as OTelStatus
    from opentelemetry.trace import StatusCode as OTelStatusCode
except ImportError:
    from typing import Any
    OTelStatus: Any = None  # type: ignore[no-redef]
    OTelStatusCode: Any = None  # type: ignore[no-redef]


class TracePhase(Enum):
    """Execution lifecycle phases."""

    INTENT_RECEIVED = "intent.received"
    POLICY_EVALUATION = "policy.evaluation"
    CAPABILITY_CHECK = "capability.check"
    INTENT_ROUTING = "intent.routing"
    TOOL_EXECUTION = "tool.execution"
    CHECKPOINT_SAVE = "checkpoint.save"
    EXECUTION_COMPLETED = "execution.completed"


@dataclass(frozen=True)
class TraceEntry:
    """A single trace entry for one execution phase."""

    phase: TracePhase
    start_time: float
    end_time: float
    duration_ms: float
    success: bool
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase.value,
            "start_time": datetime.fromtimestamp(self.start_time, tz=UTC).isoformat(),
            "end_time": datetime.fromtimestamp(self.end_time, tz=UTC).isoformat(),
            "duration_ms": round(self.duration_ms, 2),
            "success": self.success,
            "error": self.error,
            "metadata": self.metadata,
        }


class ExecutionTracer:
    """Tracks execution phases with timing and result data.

    Usage:
        tracer = ExecutionTracer(execution_id="exec-123", agent_id="a1")
        tracer.start_phase(TracePhase.POLICY_EVALUATION)
        # ... policy evaluation ...
        tracer.end_phase(success=True)

        # Get the complete trace
        trace = tracer.get_trace()
    """

    def __init__(
        self,
        execution_id: str,
        agent_id: str = "",
        intent_action: str = "",
        tenant_id: str = "",
        otel_tracer: Any | None = None,
    ) -> None:
        self._execution_id = execution_id
        self._agent_id = agent_id
        self._intent_action = intent_action
        self._tenant_id = tenant_id
        self._entries: list[TraceEntry] = []
        self._current_phase: TracePhase | None = None
        self._current_start: float = 0.0
        self._current_metadata: dict[str, Any] = {}
        self._otel_tracer = otel_tracer
        self._otel_spans: list[Any] = []

    def start_phase(
        self,
        phase: TracePhase,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Start timing a phase. If a phase is already active, it's ended automatically."""
        if self._current_phase is not None:
            self.end_phase(success=True)
        self._current_phase = phase
        self._current_start = time.time()
        self._current_metadata = metadata or {}
        if self._otel_tracer is not None:
            span = self._otel_tracer.start_span(
                phase.value,
                attributes={
                    "execution_id": self._execution_id,
                    "agent_id": self._agent_id,
                    "tenant_id": self._tenant_id,
                    "intent_action": self._intent_action,
                    **(metadata or {}),
                },
            )
            self._otel_spans.append(span)

    def end_phase(
        self,
        success: bool = True,
        error: str | None = None,
    ) -> TraceEntry:
        """End the current phase and record the trace entry."""
        if self._current_phase is None:
            raise RuntimeError("No active phase to end")

        end_time = time.time()
        duration_ms = (end_time - self._current_start) * 1000

        entry = TraceEntry(
            phase=self._current_phase,
            start_time=self._current_start,
            end_time=end_time,
            duration_ms=duration_ms,
            success=success,
            error=error,
            metadata=self._current_metadata,
        )
        self._entries.append(entry)
        if self._otel_spans:
            span = self._otel_spans.pop()
            if error and OTelStatus is not None and OTelStatusCode is not None:
                span.set_status(OTelStatus(OTelStatusCode.ERROR, error))
            span.set_attribute("duration_ms", duration_ms)
            span.set_attribute("success", str(success))
            span.end()
        self._current_phase = None
        self._current_start = 0.0
        self._current_metadata = {}
        return entry

    def get_trace(self) -> list[dict[str, Any]]:
        """Get the complete trace as a list of serialized entries."""
        return [e.to_dict() for e in self._entries]

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the execution trace."""
        total_duration = 0.0
        phases = []

        for entry in self._entries:
            total_duration += entry.duration_ms
            phases.append(entry.phase.value)

        failures = [e for e in self._entries if not e.success]

        return {
            "execution_id": self._execution_id,
            "agent_id": self._agent_id,
            "intent_action": self._intent_action,
            "tenant_id": self._tenant_id,
            "total_duration_ms": round(total_duration, 2),
            "phase_count": len(self._entries),
            "phases": phases,
            "failures": len(failures),
            "status": "failure" if failures else "success",
        }

    def clear(self) -> None:
        """Clear all trace entries."""
        self._entries.clear()
        self._current_phase = None
        self._current_start = 0.0
        self._current_metadata = {}
