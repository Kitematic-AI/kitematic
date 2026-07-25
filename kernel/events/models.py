from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class EventType(Enum):
    """Types of execution events.

    Every loop step MUST emit one of these.
    """

    LOOP_STARTED = "LOOP_STARTED"
    BUDGET_CHECKED = "BUDGET_CHECKED"
    POLICY_EVALUATED = "POLICY_EVALUATED"
    CAPABILITY_CHECKED = "CAPABILITY_CHECKED"
    INTENT_ROUTED = "INTENT_ROUTED"
    GATEWAY_ACCESSED = "GATEWAY_ACCESSED"
    TOOL_EXECUTED = "TOOL_EXECUTED"
    CHECKPOINT_SAVED = "CHECKPOINT_SAVED"
    STEP_COMPLETED = "STEP_COMPLETED"
    LOOP_TERMINATED = "LOOP_TERMINATED"
    LOOP_FAILED = "LOOP_FAILED"
    LOOP_HALTED = "LOOP_HALTED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    TIMEOUT_OCCURRED = "TIMEOUT_OCCURRED"


@dataclass(frozen=True)
class ExecutionEvent:
    """Immutable event envelope for all runtime events.

    Carries full correlation context from the execution lifecycle
    so subscribers never need to look up execution metadata externally.

    Designed to be serialized to JSON for Redis Pub/Sub, WebSocket frames,
    or persisted to an event store.
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    execution_id: str = ""
    tenant_id: str = ""
    agent_id: str | None = None
    event_type: EventType | str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    schema_version: str = "1.0"

    @property
    def metadata(self) -> dict[str, Any]:
        return dict(self.payload.get("metadata", {}))

    @property
    def error(self) -> str | None:
        err = self.payload.get("error")
        return str(err) if err is not None else None

    @property
    def state(self) -> str:
        return str(self.payload.get("state", ""))

    @property
    def step_number(self) -> int:
        return int(self.payload.get("step_number", 0))

    def to_dict(self) -> dict[str, Any]:
        ev_type = self.event_type
        if isinstance(ev_type, EventType):
            ev_type = ev_type.value
        return {
            "event_id": self.event_id,
            "execution_id": self.execution_id,
            "tenant_id": self.tenant_id,
            "agent_id": self.agent_id,
            "event_type": ev_type,
            "payload": self.payload,
            "created_at": self.created_at.isoformat(),
            "schema_version": self.schema_version,
        }


class EventLog:
    """Append-only event log for a single execution.

    This is the source of truth for execution history.
    EventPublisher is for streaming — EventLog is for replay.

    Guarantees:
      - Events are ordered by creation time
      - Events are never modified after creation
      - Complete audit trail
    """

    def __init__(self, execution_id: str):
        self.execution_id = execution_id
        self._events: list[ExecutionEvent] = []
        self._counter: int = 0

    def emit(
        self,
        event_type: EventType,
        state: str = "",
        metadata: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> ExecutionEvent:
        self._counter += 1
        event = ExecutionEvent(
            event_id=f"evt-{self.execution_id}-{self._counter:04d}",
            execution_id=self.execution_id,
            event_type=event_type,
            payload={
                "state": state,
                "step_number": self._counter,
                "metadata": metadata or {},
                "error": error,
            },
            schema_version="1.0",
        )
        self._events.append(event)
        return event

    @property
    def events(self) -> list[ExecutionEvent]:
        return list(self._events)

    @property
    def count(self) -> int:
        return len(self._events)

    @property
    def last_event(self) -> ExecutionEvent | None:
        return self._events[-1] if self._events else None

    def get_events_by_type(self, event_type: EventType) -> list[ExecutionEvent]:
        return [e for e in self._events if e.event_type == event_type]

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "event_count": self.count,
            "events": [e.to_dict() for e in self._events],
        }
