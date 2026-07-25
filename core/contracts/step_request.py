"""Step request contract — input passed from Orchestrator to Agent Worker."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StepRequest:
    """A single step execution request sent to an Agent Worker."""

    execution_id: str
    agent_id: str
    goal: str
    state: dict[str, Any] = field(default_factory=dict)
    allowed_tools: list[str] = field(default_factory=list)
    allowed_models: list[str] = field(default_factory=list)
    max_tokens: int = 50_000
    max_time_seconds: int = 3_600
