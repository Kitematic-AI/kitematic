"""Runtime Contract exceptions — typed errors for ABI-level failures.

Every exception maps to a specific failure point in the execution chain:
  - PolicyRejectionError: Policy evaluation denied the intent
  - CapabilityNotFoundError: Agent lacks required capability
  - CapabilityDeniedError: Policy denied the capability
  - OrchestrationError: Orchestrator routing failed
  - GatewayAccessError: MCP Gateway tool access failed
  - CheckpointPersistenceError: Checkpoint save/restore failed
  - InvalidStateTransitionError: Lifecycle state machine violation
"""


class RuntimeContractError(Exception):
    """Base exception for all Runtime Contract errors."""
    code: str = "RUNTIME_CONTRACT_ERROR"


class PolicyRejectionError(RuntimeContractError):
    """Raised when Policy Engine rejects an intent."""
    code = "POLICY_REJECTED"

    def __init__(self, reason: str, matched_rule: str | None = None):
        self.reason = reason
        self.matched_rule = matched_rule
        super().__init__(f"Policy rejected: {reason}")


class CapabilityNotFoundError(RuntimeContractError):
    """Raised when the agent has no capability for the requested action."""
    code = "CAPABILITY_NOT_FOUND"

    def __init__(self, action: str, agent_id: str):
        self.action = action
        self.agent_id = agent_id
        super().__init__(f"No capability for action '{action}' on agent '{agent_id}'")


class CapabilityDeniedError(RuntimeContractError):
    """Raised when Policy Engine denies a specific capability."""
    code = "CAPABILITY_DENIED"

    def __init__(self, capability_name: str, reason: str):
        self.capability_name = capability_name
        self.reason = reason
        super().__init__(f"Capability '{capability_name}' denied: {reason}")


class OrchestrationError(RuntimeContractError):
    """Raised when Orchestrator fails to route or manage execution."""
    code = "ORCHESTRATION_FAILED"

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Orchestration failed: {reason}")


class GatewayAccessError(RuntimeContractError):
    """Raised when MCP Gateway tool access fails."""
    code = "GATEWAY_ACCESS_FAILED"

    def __init__(self, tool: str, reason: str):
        self.tool = tool
        self.reason = reason
        super().__init__(f"Gateway access failed for tool '{tool}': {reason}")


class CheckpointPersistenceError(RuntimeContractError):
    """Raised when Checkpoint System fails to save or restore."""
    code = "CHECKPOINT_PERSISTENCE_FAILED"

    def __init__(self, operation: str, reason: str):
        self.operation = operation
        self.reason = reason
        super().__init__(f"Checkpoint {operation} failed: {reason}")


class RuntimeDrainingError(RuntimeContractError):
    """Raised when Runtime is draining and rejects new executions."""
    code = "RUNTIME_DRAINING"

    def __init__(self) -> None:
        super().__init__("Runtime is draining — no new executions accepted")


class RuntimeStoppedError(RuntimeContractError):
    """Raised when Runtime is stopped."""
    code = "RUNTIME_STOPPED"

    def __init__(self) -> None:
        super().__init__("Runtime is stopped")


class InvalidStateTransitionError(RuntimeContractError):
    """Raised when an invalid lifecycle state transition is attempted."""
    code = "INVALID_STATE_TRANSITION"

    def __init__(self, current: str, target: str, valid: list[str]):
        self.current = current
        self.target = target
        self.valid = valid
        super().__init__(
            f"Invalid transition: {current} → {target}. "
            f"Valid: {valid}"
        )
