"""Step response contract — result returned from Agent Worker to Orchestrator."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StepStatus(Enum):
    COMPLETED = "COMPLETED"
    TOOL_REQUEST = "TOOL_REQUEST"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    CHECKPOINT_REQUIRED = "CHECKPOINT_REQUIRED"
    FAILED = "FAILED"


@dataclass
class ToolRequest:
    """A request to execute an external tool via MCP Gateway."""

    mcp_server: str
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResponse:
    """Result of executing one Agent step."""

    status: StepStatus
    updated_state: dict[str, Any] = field(default_factory=dict)
    output: str = ""
    tool_request: ToolRequest | None = None
    error_message: str = ""
    tokens_consumed: int = 0
