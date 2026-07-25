"""Runtime event streaming — stream chunks and plugin lifecycle events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class StreamChunk:
    """A single chunk of a streaming response."""

    content: str | None = None
    finish_reason: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class RuntimeEvent:
    """A plugin lifecycle event — emitted on state transitions.

    Used for audit trails, observability, and real-time monitoring.
    """

    plugin_name: str
    event_type: str
    timestamp: datetime
    metadata: dict[str, Any] = None
