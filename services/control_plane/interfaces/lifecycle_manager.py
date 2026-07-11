"""Lifecycle Manager interface — Agent lifecycle orchestration."""

from abc import ABC, abstractmethod


class LifecycleManager(ABC):
    """Manages Agent lifecycle: start, stop, pause, resume, scale."""

    @abstractmethod
    async def start_execution(
        self, agent_instance_id: str, goal: str
    ) -> str:
        """Start a new execution. Returns execution_id."""
        ...

    @abstractmethod
    async def stop_execution(self, execution_id: str) -> None:
        """Stop execution and save final checkpoint."""
        ...

    @abstractmethod
    async def pause_execution(self, execution_id: str) -> None:
        """Pause execution mid-step."""
        ...

    @abstractmethod
    async def resume_execution(self, execution_id: str) -> None:
        """Resume from last checkpoint."""
        ...

    @abstractmethod
    async def get_execution_status(self, execution_id: str) -> str:
        """Return current execution status."""
        ...
