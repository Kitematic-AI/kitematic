"""Tests for RuntimeExecutorProtocol."""

from typing import Any

from core.contracts.runtime import RuntimeExecutorProtocol
from core.domain.execution_context import ExecutionContext


class TestRuntimeExecutorProtocol:
    def test_protocol_exists(self) -> None:
        assert RuntimeExecutorProtocol is not None

    def test_conforming_executor_passes_isinstance(self) -> None:
        class GoodExecutor:
            async def execute(
                self,
                plugin_name: str,
                payload: dict[str, Any],
                context: ExecutionContext,
            ) -> dict[str, Any]:
                return {}

        assert isinstance(GoodExecutor(), RuntimeExecutorProtocol)

    def test_non_conforming_class_fails_isinstance(self) -> None:
        class Bad:
            pass

        assert not isinstance(Bad(), RuntimeExecutorProtocol)
