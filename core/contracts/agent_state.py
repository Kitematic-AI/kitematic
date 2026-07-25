"""Agent state contract — serializable state that moves between steps."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentState:
    """Serializable state for an Agent execution."""

    execution_id: str
    agent_id: str
    current_node: str = ""
    step_number: int = 0
    data: dict[str, Any] = field(default_factory=dict)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    memory_refs: list[str] = field(default_factory=list)
