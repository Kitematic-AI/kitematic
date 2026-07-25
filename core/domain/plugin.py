"""PluginManifest domain model — the canonical representation of any plugin.

All plugins (tools, frameworks, models, agents) share this single manifest.
The kernel never references vendor names like "langgraph" or "claude" —
it only reads PluginType, capabilities, and permissions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PluginType(Enum):
    AGENT = "agent"
    TOOL = "tool"
    MODEL = "model"
    FRAMEWORK = "framework"


@dataclass(frozen=True)
class PluginManifest:
    """Complete plugin definition — the single entry point for all plugins."""

    name: str
    version: str
    plugin_type: PluginType
    runtime_type: str
    description: str
    author: str
    entrypoint: dict[str, str]
    capabilities: list[dict[str, Any]] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    min_kernel_version: str = "1.0.0"
    config_schema: dict[str, Any] | None = None
    provider: dict[str, Any] | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.name:
            errors.append("name is required")
        if not self.version:
            errors.append("version is required")
        if "module" not in self.entrypoint:
            errors.append("entrypoint.module is required")
        if "class" not in self.entrypoint:
            errors.append("entrypoint.class is required")
        if not self.runtime_type:
            errors.append("runtime_type is required")
        return errors

    @property
    def is_valid(self) -> bool:
        return len(self.validate()) == 0
