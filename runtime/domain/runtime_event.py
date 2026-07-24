"""Runtime event streaming."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StreamChunk:
    """A single chunk of a streaming response."""

    content: str | None = None
    finish_reason: str | None = None
    metadata: dict[str, Any] = None