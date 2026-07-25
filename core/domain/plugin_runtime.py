"""Plugin runtime record — persisted state for loaded plugins.

Each running (or failed/stopped) plugin has a corresponding record
tracking its lifecycle state, timestamps, and last error.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class PluginRuntimeState(Enum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class PluginRuntimeRecord:
    name: str
    version: str
    state: PluginRuntimeState = PluginRuntimeState.CREATED
    loaded_at: datetime | None = None
    last_health_check: datetime | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
