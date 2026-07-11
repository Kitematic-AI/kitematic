"""Orchestration-specific errors for the Control Plane."""


class OrchestrationError(Exception):
    """Base error for orchestration failures."""


class ExecutionNotFoundError(OrchestrationError):
    """Raised when an execution ID does not exist."""
    def __init__(self, execution_id: str):
        self.execution_id = execution_id
        super().__init__(f"Execution not found: {execution_id}")


class AgentInstanceNotFoundError(OrchestrationError):
    """Raised when an agent instance ID does not exist."""
    def __init__(self, instance_id: str):
        self.instance_id = instance_id
        super().__init__(f"Agent instance not found: {instance_id}")


class ManifestValidationError(OrchestrationError):
    """Raised when an agent manifest fails validation."""
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Manifest validation failed: {'; '.join(errors)}")


class PolicyViolationError(OrchestrationError):
    """Raised when a step is blocked by policy."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Policy violation: {reason}")
