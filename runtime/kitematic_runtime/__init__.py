"""KitematicRuntime — the top-level execution ABI.

Orchestrates the full chain:
  Intent → Policy → Orchestrator → Gateway → Checkpoint

Runtime executes lifecycle only. Never decides. Never bypasses Gateway.
"""

from kernel.resources.budget import ExecutionBudget
from kernel.events import EventLog, EventType, ExecutionEvent
from kernel.exceptions import (
    CapabilityDeniedError,
    CapabilityNotFoundError,
    CheckpointPersistenceError,
    GatewayAccessError,
    InvalidStateTransitionError,
    OrchestrationError,
    PolicyRejectionError,
    RuntimeContractError,
)
from kernel.gateway import (
    GatewayAuditEntry,
    MCPClientNotFoundError,
    MCPToolGateway,
)
from kernel.isolation import (
    AgentNotInTenantError,
    CrossAgentAccessError,
    CrossTenantAccessError,
    IsolationBoundary,
    IsolationError,
    MissingTenantContextError,
    ResourceLimitExceededError,
    TenantNotFoundError,
)
from kernel.lifecycle import LoopController, LoopResult, LoopTermination
from kernel.runtime import KitematicRuntime
from kernel.state import VALID_TRANSITIONS, ExecutionState
from kernel.tenant import ResourceLimits, TenantContext, TenantModel
from kernel.resources.tool_registry import (
    ToolAlreadyRegisteredError,
    ToolCapabilityMismatchError,
    ToolDefinition,
    ToolNotFoundError,
    ToolRegistry,
)

__all__ = [
    "ExecutionState",
    "VALID_TRANSITIONS",
    "KitematicRuntime",
    "ExecutionBudget",
    "ExecutionEvent",
    "EventLog",
    "EventType",
    "LoopController",
    "LoopResult",
    "LoopTermination",
    "RuntimeContractError",
    "PolicyRejectionError",
    "CapabilityNotFoundError",
    "CapabilityDeniedError",
    "OrchestrationError",
    "GatewayAccessError",
    "CheckpointPersistenceError",
    "InvalidStateTransitionError",
    # Tenant Isolation
    "TenantModel",
    "TenantContext",
    "ResourceLimits",
    "IsolationBoundary",
    "IsolationError",
    "TenantNotFoundError",
    "AgentNotInTenantError",
    "CrossTenantAccessError",
    "CrossAgentAccessError",
    "MissingTenantContextError",
    "ResourceLimitExceededError",
    # MCP Gateway
    "ToolDefinition",
    "ToolRegistry",
    "ToolNotFoundError",
    "ToolAlreadyRegisteredError",
    "ToolCapabilityMismatchError",
    "MCPToolGateway",
    "MCPClientNotFoundError",
    "GatewayAuditEntry",
]
