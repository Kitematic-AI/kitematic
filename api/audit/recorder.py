"""Audit — security event recording with correlation context.

Records security-relevant events (auth failures, tenant violations, key rotation)
with full correlation context matching the existing ExecutionEvent model and
RuntimeLogger patterns.

AuditEvent is a lightweight dataclass (not pydantic frozen) to avoid
pulling pydantic into every audit path at runtime. Correlation fields
match those in ObservabilityContext for distributed tracing alignment.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from kernel.observability.logging import RuntimeLogger


class AuditEventType(Enum):
    AUTH_SUCCESS = "auth.success"
    AUTH_FAILURE = "auth.failure"
    KEY_ROTATION = "auth.key_rotation"
    TENANT_DENIED = "tenant.denied"
    WEBSOCKET_DEPRECATED = "websocket.deprecated_auth"


@dataclass
class AuditEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: AuditEventType = AuditEventType.AUTH_FAILURE
    tenant_id: str = ""
    agent_id: str = ""
    execution_id: str = ""
    detail: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class AuditRecorder:
    """Records security audit events through RuntimeLogger.

    Every audit event is logged as a structured JSON line with:
      - event_id (unique, for traceability)
      - event_type (from AuditEventType)
      - tenant_id, agent_id, execution_id (correlation context)
      - detail (human-readable description)

    No separate storage — audit lives in the same log stream as runtime events.
    """

    def __init__(self, logger: RuntimeLogger | None = None) -> None:
        self._logger = logger

    def record(self, event: AuditEvent) -> None:
        if self._logger:
            self._logger.info(
                event.detail or event.event_type.value,
                audit_event_id=event.event_id,
                audit_event_type=event.event_type.value,
                tenant_id=event.tenant_id,
                agent_id=event.agent_id,
                execution_id=event.execution_id,
            )

    def record_auth_failure(self, tenant_id: str = "", detail: str = "") -> AuditEvent:
        event = AuditEvent(
            event_type=AuditEventType.AUTH_FAILURE,
            tenant_id=tenant_id,
            detail=detail or "Authentication failed",
        )
        self.record(event)
        return event

    def record_auth_success(self, tenant_id: str = "", agent_id: str = "") -> AuditEvent:
        event = AuditEvent(
            event_type=AuditEventType.AUTH_SUCCESS,
            tenant_id=tenant_id,
            agent_id=agent_id,
            detail="Authentication succeeded",
        )
        self.record(event)
        return event

    def record_key_rotation(self, tenant_id: str = "", detail: str = "") -> AuditEvent:
        event = AuditEvent(
            event_type=AuditEventType.KEY_ROTATION,
            tenant_id=tenant_id,
            detail=detail or "API key rotated",
        )
        self.record(event)
        return event

    def record_tenant_denied(
        self, tenant_id: str = "", execution_id: str = "", detail: str = ""
    ) -> AuditEvent:
        event = AuditEvent(
            event_type=AuditEventType.TENANT_DENIED,
            tenant_id=tenant_id,
            execution_id=execution_id,
            detail=detail or "Cross-tenant access denied",
        )
        self.record(event)
        return event

    def record_websocket_deprecated(
        self, tenant_id: str = "", detail: str = ""
    ) -> AuditEvent:
        event = AuditEvent(
            event_type=AuditEventType.WEBSOCKET_DEPRECATED,
            tenant_id=tenant_id,
            detail=detail or "WebSocket deprecated auth method used",
        )
        self.record(event)
        return event
