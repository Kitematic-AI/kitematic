"""Pydantic contracts for the Runtime API layer.

These mirror the runtime DTOs (Intent, ExecutionResult, etc.) but add
HTTP-specific validation, serialization, and documentation.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ── Request Models ────────────────────────────────────────────────


class IntentRequest(BaseModel):
    """Request body for submitting an intent to the Runtime."""

    agent_id: str = Field(..., min_length=1, description="ID of the submitting agent")
    action: str = Field(..., min_length=1, description="Action to execute")
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Optional action parameters"
    )


class TenantHeaders(BaseModel):
    """Extracted from X-Tenant-ID / X-Agent-ID request headers."""

    tenant_id: str = Field(default="", description="Tenant identifier")
    agent_id: str = Field(default="", description="Agent identifier")


# ── Response Models ───────────────────────────────────────────────


class ExecutionResponse(BaseModel):
    """Response after submitting an intent for execution."""

    execution_id: str
    success: bool
    state: str
    checkpoint_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ExecutionStatusResponse(BaseModel):
    """Status of a previously submitted execution."""

    execution_id: str
    state: str
    agent_id: str
    action: str
    success: bool
    error: str | None = None


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: str
    code: str = "RUNTIME_CONTRACT_ERROR"
    details: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str = "1.0.0-rc.1"
    runtime: str = "kitematic-runtime"


class MetricsResponse(BaseModel):
    """Runtime metrics snapshot."""

    counters: dict[str, int] = Field(default_factory=dict)
    histograms: dict[str, dict[str, float]] = Field(default_factory=dict)
    gauges: dict[str, Any] = Field(default_factory=dict)
