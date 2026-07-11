"""Orchestrator interface — the core state machine for step execution."""

from abc import ABC, abstractmethod
from typing import Any


class Orchestrator(ABC):
    """Coordinates step-by-step Agent execution."""

    @abstractmethod
    async def execute_step(
        self,
        execution_id: str,
        agent_id: str,
        state: dict[str, Any],
        goal: str,
    ) -> dict[str, Any]:
        """Execute one step of an Agent's plan.

        Returns a StepResponse indicating COMPLETED, TOOL_REQUEST,
        APPROVAL_REQUIRED, or FAILED.
        """
        ...

    @abstractmethod
    async def pause_execution(self, execution_id: str) -> None:
        """Pause execution and save checkpoint."""
        ...

    @abstractmethod
    async def resume_execution(
        self, execution_id: str, checkpoint_id: str
    ) -> dict[str, Any]:
        """Resume execution from a saved checkpoint."""
        ...

    @abstractmethod
    async def cancel_execution(self, execution_id: str) -> None:
        """Cancel execution permanently."""
        ...
