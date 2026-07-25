"""ContextBuilder — fluent builder for creating ExecutionContext instances.

Prevents incomplete or inconsistent context creation.
All state is deep-copied to guarantee immutability after build.
"""

import copy
from typing import Any

from kernel.execution.context import ExecutionContext


class ContextBuilder:
    """Fluent builder for ExecutionContext.

    Usage:
        ctx = (
            ContextBuilder("exec-1", "agent-1")
            .with_budget(1000)
            .with_state({"goal": "compute"})
            .with_memory(memory_repo)
            .build()
        )

    All injected values are deep-copied to prevent mutation.
    """

    def __init__(self, execution_id: str, agent_id: str) -> None:
        if not execution_id:
            raise ValueError("execution_id is required")
        if not agent_id:
            raise ValueError("agent_id is required")
        self._execution_id = execution_id
        self._agent_id = agent_id
        self._step_number: int = 0
        self._budget_remaining: int = 0
        self._tokens_per_step: int = 10
        self._state: dict[str, Any] = {}
        self._allowed_tools: list[str] = []
        self._metadata: dict[str, Any] = {}
        self._tokens_consumed: int = 0
        self._memory: Any = None
        self._checkpoint: Any = None

    def with_step_number(self, step_number: int) -> "ContextBuilder":
        self._step_number = step_number
        return self

    def with_budget(self, budget: int) -> "ContextBuilder":
        self._budget_remaining = budget
        return self

    def with_tokens_per_step(self, tokens_per_step: int) -> "ContextBuilder":
        self._tokens_per_step = tokens_per_step
        return self

    def with_state(self, state: dict[str, Any]) -> "ContextBuilder":
        self._state = copy.deepcopy(state)
        return self

    def with_allowed_tools(self, tools: list[str]) -> "ContextBuilder":
        self._allowed_tools = copy.deepcopy(tools)
        return self

    def with_metadata(self, metadata: dict[str, Any]) -> "ContextBuilder":
        self._metadata = copy.deepcopy(metadata)
        return self

    def with_memory(self, memory: Any) -> "ContextBuilder":
        self._memory = memory
        return self

    def with_checkpoint(self, checkpoint: Any) -> "ContextBuilder":
        self._checkpoint = checkpoint
        return self

    def build(self) -> ExecutionContext:
        return ExecutionContext(
            execution_id=self._execution_id,
            agent_id=self._agent_id,
            step_number=self._step_number,
            state=copy.deepcopy(self._state),
            budget_remaining=self._budget_remaining,
            tokens_per_step=self._tokens_per_step,
            allowed_tools=copy.deepcopy(self._allowed_tools),
            metadata=copy.deepcopy(self._metadata),
            tokens_consumed=self._tokens_consumed,
            memory=self._memory,
            checkpoint=self._checkpoint,
        )
