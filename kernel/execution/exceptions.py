"""Runtime exceptions — typed errors for execution failures."""



class RuntimeExecutionError(Exception):
    """Base exception for runtime execution failures."""
    code: str = "RUNTIME_ERROR"


class InvalidStepRequestError(RuntimeExecutionError):
    """Raised when a step request is missing required fields or has invalid data."""
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Invalid step request: {'; '.join(errors)}")
        self.code = "INVALID_REQUEST"


class BudgetExceededError(RuntimeExecutionError):
    """Raised when execution exceeds its token budget."""
    def __init__(self, limit: int, consumed: int):
        self.limit = limit
        self.consumed = consumed
        super().__init__(f"Budget exceeded: {consumed} > {limit}")
        self.code = "BUDGET_EXCEEDED"


class NodeExecutionError(RuntimeExecutionError):
    """Raised when internal step processing fails."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Node execution failed: {reason}")
        self.code = "NODE_EXECUTION_FAILED"
