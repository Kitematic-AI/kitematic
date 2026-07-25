"""AI Gateway interface definitions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class Gateway(ABC):
    """Gateway interface for model provider orchestration."""

    @abstractmethod
    async def execute(self, request: dict) -> dict:
        """Execute a single request."""
        ...

    @abstractmethod
    async def execute_stream(
        self, request: dict
    ) -> AsyncIterator:
        """Execute a request with streaming response."""
        ...

    @abstractmethod
    def get_capabilities(self) -> tuple[str, ...]:
        """Return supported capabilities."""
        ...

    @abstractmethod
    async def health_check(self) -> dict:
        """Check gateway health."""
        ...

    @abstractmethod
    def supports(self, required_capabilities: frozenset[str]) -> bool:
        """Check if gateway supports required capabilities."""
        ...
