"""API Layer — FastAPI-based HTTP and WebSocket interface for KitematicRuntime.

Thin transport layer only. Never makes policy/authorization decisions.

Modules:
  - schemas: Pydantic contracts for request/response validation
  - auth: AuthProvider ABC + APIKeyAuthProvider
  - audit: AuditRecorder for security event recording
  - events: EventPublisher for WebSocket streaming
  - app: FastAPI application factory with REST + WebSocket routes
"""

from runtime.kitematic_runtime.api.app import create_app
from runtime.kitematic_runtime.api.audit import AuditEvent, AuditEventType, AuditRecorder
from runtime.kitematic_runtime.api.auth import (
    APIKeyAuthProvider,
    AuthContext,
    AuthProvider,
)
from runtime.kitematic_runtime.api.events import EventPublisher
from runtime.kitematic_runtime.api.schemas import (
    ErrorResponse,
    ExecutionResponse,
    ExecutionStatusResponse,
    HealthResponse,
    IntentRequest,
    MetricsResponse,
)

__all__ = [
    "IntentRequest",
    "ExecutionResponse",
    "ExecutionStatusResponse",
    "ErrorResponse",
    "HealthResponse",
    "MetricsResponse",
    "AuthProvider",
    "APIKeyAuthProvider",
    "AuthContext",
    "AuditRecorder",
    "AuditEvent",
    "AuditEventType",
    "EventPublisher",
    "create_app",
]
