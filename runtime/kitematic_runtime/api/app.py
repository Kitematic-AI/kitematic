"""FastAPI application factory — REST + WebSocket API for KitematicRuntime.

Thin transport layer only. Never makes policy/authorization decisions.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from runtime.kitematic_runtime.api.auth import APIKeyAuthProvider, AuthContext, AuthProvider
from runtime.kitematic_runtime.api.schemas import (
    ErrorResponse,
    ExecutionResponse,
    ExecutionStatusResponse,
    HealthResponse,
    IntentRequest,
    MetricsResponse,
)
from runtime.kitematic_runtime.config.settings import RuntimeSettings
from kernel.events import EventPublisher, ExecutionEvent, create_event_publisher
from kernel.observability.metrics import MetricsRegistry
from kernel.runtime import Intent, KitematicRuntime

_log = logging.getLogger(__name__)


def get_auth_dependency(
    auth_provider: AuthProvider,
    metrics: MetricsRegistry | None = None,
) -> Callable[[Request], Coroutine[Any, Any, AuthContext]]:
    """Factory for the auth dependency — extracts X-API-Key and resolves AuthContext."""

    async def _get_auth_context(request: Request) -> AuthContext:
        api_key = request.headers.get("X-API-Key", "")
        ctx = await auth_provider.authenticate(api_key)
        if ctx is None:
            if metrics:
                metrics.increment("security.auth.failed")
            raise HTTPException(status_code=401, detail="Invalid or missing API key")
        return ctx

    return _get_auth_context


async def _ws_authenticate(
    auth_provider: AuthProvider,
    websocket: WebSocket,
    api_key: str,
    metrics: MetricsRegistry | None = None,
) -> AuthContext | None:
    """Authenticate a WebSocket connection.

    Priority:
      1. Authorization: Bearer <token> header
      2. Sec-WebSocket-Protocol: kitematic.<token> header
      3. api_key query param (deprecated — logs warning + increments security.websocket.deprecated)
    """
    # 1. Authorization: Bearer <token>
    auth_header = websocket.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        return await auth_provider.authenticate(token)

    # 2. Sec-WebSocket-Protocol: kitematic.<token>
    ws_protocol = websocket.headers.get("sec-websocket-protocol", "")
    if ws_protocol and ws_protocol.startswith("kitematic."):
        token = ws_protocol[len("kitematic."):]
        ctx = await auth_provider.authenticate(token)
        if ctx is not None:
            return ctx

    # 3. Deprecated: api_key query param
    if api_key:
        ctx = await auth_provider.authenticate(api_key)
        if ctx is not None:
            _log.warning(
                "WebSocket auth via query param is deprecated. "
                "Use 'Authorization: Bearer <token>' header or "
                "'Sec-WebSocket-Protocol: kitematic.<token>' header instead.",
            )
            if metrics:
                metrics.increment("security.websocket.deprecated")
            return ctx

    return None


def create_app(
    runtime: KitematicRuntime,
    auth_provider: AuthProvider | None = None,
    event_publisher: EventPublisher | None = None,
    metrics_registry: MetricsRegistry | None = None,
    settings: RuntimeSettings | None = None,
) -> FastAPI:
    """Create a FastAPI application wired to a KitematicRuntime instance.

    Args:
        runtime: The KitematicRuntime instance to serve.
        auth_provider: Optional auth provider. Defaults to an empty APIKeyAuthProvider.
        event_publisher: Optional EventPublisher for WebSocket event streaming.
        metrics_registry: Optional MetricsRegistry for /metrics endpoint.
        settings: Optional RuntimeSettings. Defaults to RuntimeSettings().

    Returns:
        Configured FastAPI application.
    """
    if auth_provider is None:
        auth_provider = APIKeyAuthProvider()

    app_settings = settings or RuntimeSettings()

    if event_publisher is None:
        event_publisher = create_event_publisher(app_settings)

    if metrics_registry is None:
        metrics_registry = MetricsRegistry()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """FastAPI lifespan — manages startup and shutdown lifecycle.

        Startup:
          - Records startup time
          - Logs API version

        Shutdown (order matters):
          1. Stop accepting new API requests (by rejecting new Runtime executions)
          2. Close event publisher queues (safe after Runtime stop)
        """
        app.state.startup_time = datetime.now(UTC)
        if hasattr(runtime, "_logger") and runtime._logger:
            runtime._logger.info("API starting", version=app_settings.api_version)
        yield
        if hasattr(runtime, "_logger") and runtime._logger:
            runtime._logger.info("API shutting down")
        await runtime.stop()
        event_publisher.close_all()
        if hasattr(runtime, "_logger") and runtime._logger:
            runtime._logger.info("API shutdown complete")

    app = FastAPI(
        title=app_settings.api_title,
        version=app_settings.api_version,
        description="Runtime API for intent execution and event streaming",
        lifespan=lifespan,
    )

    # State
    app.state.runtime = runtime
    app.state.auth_provider = auth_provider
    app.state.event_publisher = event_publisher
    app.state.metrics_registry = metrics_registry
    app.state.executions = {}

    get_auth_context = get_auth_dependency(auth_provider, metrics_registry)

    # ── Exception Handlers ────────────────────────────────────────

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error=str(exc),
                code="INTERNAL_ERROR",
            ).model_dump(),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=exc.detail,
                code=_status_code_to_code(exc.status_code),
            ).model_dump(),
        )

    # ── REST Endpoints ────────────────────────────────────────────

    @app.post("/api/v1/intents", status_code=201)
    async def submit_intent(
        intent_req: IntentRequest,
        auth: AuthContext = Depends(get_auth_context),
        x_tenant_id: str = "",
        x_agent_id: str = "",
    ) -> ExecutionResponse:
        """Submit an intent to the Kitematic Runtime for execution.

        Requires X-API-Key header for authentication.
        Optional X-Tenant-ID and X-Agent-ID headers for tenant context.
        """
        # Build tenant context from headers or auth context
        tenant_id = x_tenant_id or auth.tenant_id
        agent_id = x_agent_id or auth.agent_id or intent_req.agent_id

        intent = Intent(
            agent_id=intent_req.agent_id,
            action=intent_req.action,
            parameters=intent_req.parameters,
        )

        # Execute through runtime
        result = await runtime.execute_intent(intent)

        # Store execution for later lookup
        execution_record: dict[str, Any] = {
            "execution_id": result.execution_id,
            "success": result.success,
            "state": result.state.value,
            "agent_id": intent_req.agent_id,
            "action": intent_req.action,
            "tenant_id": tenant_id,
            "checkpoint_id": result.checkpoint_id,
            "error": result.error,
            "created_at": datetime.now(UTC).isoformat(),
        }
        app.state.executions[result.execution_id] = execution_record

        # Track metrics
        metrics_registry.increment("api.intents_submitted")
        if result.success:
            metrics_registry.increment("api.intents_succeeded")
        else:
            metrics_registry.increment("api.intents_failed")

        # Publish execution lifecycle events
        event = ExecutionEvent(
            execution_id=result.execution_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            event_type="execution.completed",
            payload={
                "success": result.success,
                "state": result.state.value,
                "error": result.error,
            },
        )
        await event_publisher.publish(event)

        return ExecutionResponse(
            execution_id=result.execution_id,
            success=result.success,
            state=result.state.value,
            checkpoint_id=result.checkpoint_id,
            data=result.data,
            error=result.error,
        )

    @app.get("/api/v1/executions/{execution_id}")
    async def get_execution_status(
        execution_id: str,
        auth: AuthContext = Depends(get_auth_context),
    ) -> ExecutionStatusResponse:
        """Get the status of a previously submitted execution.

        Tenant isolation: a tenant can only see its own executions.
        Returns 403 (not 404) to prevent execution ID enumeration.
        """
        record = app.state.executions.get(execution_id)
        if record is None:
            raise HTTPException(status_code=403, detail="Execution not found or access denied")

        if record.get("tenant_id") and record["tenant_id"] != auth.tenant_id:
            metrics_registry.increment("security.tenant.denied")
            raise HTTPException(status_code=403, detail="Execution not found or access denied")

        return ExecutionStatusResponse(
            execution_id=record["execution_id"],
            state=record["state"],
            agent_id=record["agent_id"],
            action=record["action"],
            success=record["success"],
            error=record["error"],
        )

    @app.get("/api/v1/health")
    async def health_check() -> HealthResponse:
        """Health check endpoint (no auth required)."""
        return HealthResponse()

    @app.get("/api/v1/metrics")
    async def get_metrics(
        auth: AuthContext = Depends(get_auth_context),
    ) -> MetricsResponse:
        """Get runtime metrics snapshot."""
        snap = metrics_registry.snapshot()
        return MetricsResponse(
            counters=snap["counters"],
            histograms=snap["histograms"],
            gauges=snap["gauges"],
        )

    # ── WebSocket Endpoint ────────────────────────────────────────

    @app.websocket("/ws/v1/executions/{execution_id}/events")
    async def execution_events(
        websocket: WebSocket,
        execution_id: str,
        api_key: str = Query(default=""),
    ) -> None:
        """Stream execution events via WebSocket.

        Authentication (in priority order):
          - Authorization: Bearer <token> header  (preferred)
          - Sec-WebSocket-Protocol: kitematic.<token> header
          - api_key query param  (deprecated — use one of the above)
        """
        ctx = await _ws_authenticate(auth_provider, websocket, api_key, metrics_registry)
        if ctx is None:
            await websocket.close(code=4001)
            return

        await websocket.accept()
        queue = event_publisher.subscribe(execution_id, ctx.tenant_id)

        async def listen_queue() -> None:
            """Send events from the publisher queue to the WebSocket."""
            while True:
                event = await queue.get()
                if event is None:
                    break
                await websocket.send_json(event)
            await websocket.send_json({
                "type": "stream.ended",
                "execution_id": execution_id,
            })

        listen_task = asyncio.create_task(listen_queue())

        try:
            while True:
                msg = await websocket.receive()
                if msg["type"] == "websocket.disconnect":
                    break
        except WebSocketDisconnect:
            pass
        finally:
            listen_task.cancel()
            event_publisher.unsubscribe(execution_id, queue)

    return app


def _status_code_to_code(status_code: int) -> str:
    """Map HTTP status code to error code string."""
    mapping = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        500: "INTERNAL_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }
    return mapping.get(status_code, "UNKNOWN")
