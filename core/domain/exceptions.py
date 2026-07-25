"""Domain exceptions — typed errors for domain-layer validation and business rule violations."""


class KitematicDomainError(Exception):
    """Base exception for all domain errors."""
    code: str = "DOMAIN_ERROR"


class ValidationError(KitematicDomainError):
    """Raised when a domain model fails validation."""
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


class PolicyViolationError(KitematicDomainError):
    """Raised when an action is denied by policy."""
    def __init__(self, reason: str, matched_rule: str | None = None):
        self.reason = reason
        self.matched_rule = matched_rule
        super().__init__(f"Policy violation: {reason}")


class BudgetExceededError(KitematicDomainError):
    """Raised when an execution exceeds its budget."""
    def __init__(self, budget_type: str, limit: float, actual: float):
        self.budget_type = budget_type
        self.limit = limit
        self.actual = actual
        super().__init__(f"{budget_type} budget exceeded: {actual} > {limit}")


class ApprovalRequiredError(KitematicDomainError):
    """Raised when an action requires human approval before proceeding."""
    def __init__(self, approval_id: str, action: str, risk_level: str):
        self.approval_id = approval_id
        self.action = action
        self.risk_level = risk_level
        super().__init__(f"Approval required for {action} (risk: {risk_level})")


class AdapterNotFoundError(KitematicDomainError):
    """Raised when a required adapter is not registered."""
    def __init__(self, adapter_name: str):
        self.adapter_name = adapter_name
        super().__init__(f"Adapter not found: {adapter_name}")


class StateConflictError(KitematicDomainError):
    """Raised when an execution state transition is invalid."""
    def __init__(self, current: str, target: str):
        self.current = current
        self.target = target
        super().__init__(f"Invalid state transition: {current} → {target}")
