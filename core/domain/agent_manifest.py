"""DEPRECATED — Use PluginManifest with plugin_type=AGENT instead.

This module exists for backward compatibility during the Phase 7 transition.
All new code should use PluginManifest from core.domain.plugin.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class AgentStatus(Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


@dataclass(frozen=True)
class AgentIdentity:
    """Identity and role of an Agent."""
    name: str
    role: str
    goal: str


@dataclass(frozen=True)
class RuntimeDefinition:
    """Which framework and entrypoint the Agent uses."""
    framework: str  # langgraph, crewai, custom
    entrypoint: str
    runtime_contract_version: str = "1.0"


@dataclass(frozen=True)
class Capabilities:
    """Allowed tools and models for the Agent."""
    allowed_tools: tuple[str, ...] = ()
    allowed_models: tuple[str, ...] = ()


@dataclass(frozen=True)
class Constraints:
    """Budget and loop limits for the Agent."""
    max_budget_usd: float = 10.0
    max_loops: int = 100
    max_tokens_per_run: int = 100_000
    human_escalation_triggers: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgentManifest:
    """Complete Agent definition — the canonical representation."""

    agent_id: str
    version: str
    tenant_id: str
    identity: AgentIdentity
    runtime_definition: RuntimeDefinition
    capabilities: Capabilities
    constraints: Constraints
    policy_profile: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def validate(self) -> list[str]:
        """Validate manifest integrity. Returns list of validation errors."""
        errors: list[str] = []

        if not self.agent_id:
            errors.append("agent_id is required")
        if not self.version:
            errors.append("version is required")
        if not self.tenant_id:
            errors.append("tenant_id is required")
        if not self.identity.name:
            errors.append("identity.name is required")
        if not self.runtime_definition.framework:
            errors.append("runtime_definition.framework is required")
        if self.constraints.max_budget_usd < 0:
            errors.append("max_budget_usd must be >= 0")
        if self.constraints.max_loops < 1:
            errors.append("max_loops must be >= 1")

        return errors

    @property
    def is_valid(self) -> bool:
        return len(self.validate()) == 0
