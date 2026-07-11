"""Adapter domain model — Adapter Registry definitions and capabilities."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class AdapterType(Enum):
    FRAMEWORK = "FRAMEWORK"
    MODEL = "MODEL"
    TOOL = "TOOL"
    MCP = "MCP"
    MEMORY = "MEMORY"
    EXECUTOR = "EXECUTOR"


class TrustLevel(Enum):
    T0_UNKNOWN = "T0_UNKNOWN"
    T1_COMMUNITY = "T1_COMMUNITY"
    T2_TESTED = "T2_TESTED"
    T3_ENTERPRISE = "T3_ENTERPRISE"
    T4_CRITICAL = "T4_CRITICAL"


@dataclass(frozen=True)
class Adapter:
    """A registered adapter in the Kitematic ecosystem."""

    adapter_id: str
    name: str
    type: AdapterType
    provider: str
    version: str
    trust_level: TrustLevel
    capabilities: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    status: str = "active"  # active, deprecated, retired
    created_at: datetime | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.adapter_id:
            errors.append("adapter_id is required")
        if not self.name:
            errors.append("name is required")
        return errors

    @property
    def is_valid(self) -> bool:
        return len(self.validate()) == 0

    @property
    def is_trusted(self) -> bool:
        return self.trust_level.value >= TrustLevel.T2_TESTED.value
