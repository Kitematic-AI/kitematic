"""KitematicRuntime — the top-level execution ABI.

Orchestrates the full chain:
  Intent → Policy → Orchestrator → Gateway → Checkpoint

Runtime executes lifecycle only. Never decides. Never bypasses Gateway.
"""

from runtime.kitematic_runtime.budget import ExecutionBudget
from runtime.kitematic_runtime.events import EventLog, EventType, ExecutionEvent
from runtime.kitematic_runtime.exceptions import (
    CapabilityDeniedError,
    CapabilityNotFoundError,
    CheckpointPersistenceError,
    GatewayAccessError,
    InvalidStateTransitionError,
    OrchestrationError,
    PolicyRejectionError,
    RuntimeContractError,
)
from runtime.kitematic_runtime.gateway import (
    GatewayAuditEntry,
    MCPClientNotFoundError,
    MCPToolGateway,
)
from runtime.kitematic_runtime.isolation import (
    AgentNotInTenantError,
    CrossAgentAccessError,
    CrossTenantAccessError,
    IsolationBoundary,
    IsolationError,
    MissingTenantContextError,
    ResourceLimitExceededError,
    TenantNotFoundError,
)
from runtime.kitematic_runtime.loop import LoopController, LoopResult, LoopTermination
from runtime.kitematic_runtime.runtime import KitematicRuntime
from runtime.kitematic_runtime.states import VALID_TRANSITIONS, ExecutionState
from runtime.kitematic_runtime.tenant import ResourceLimits, TenantContext, TenantModel
from runtime.kitematic_runtime.tool_registry import (
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
