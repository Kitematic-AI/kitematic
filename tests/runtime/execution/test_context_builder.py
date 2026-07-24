"""Unit tests for ContextBuilder — fluent builder for ExecutionContext."""

import pytest

from runtime.execution.context_builder import ContextBuilder


class TestContextBuilderDefaults:
    @pytest.mark.asyncio
    async def test_builds_with_required_fields(self) -> None:
        ctx = ContextBuilder("exec-1", "agent-1").build()
        assert ctx.execution_id == "exec-1"
        assert ctx.agent_id == "agent-1"
        assert ctx.step_number == 0
        assert ctx.budget_remaining == 0
        assert ctx.state == {}
        assert ctx.tokens_consumed == 0
        assert ctx.memory is None
        assert ctx.checkpoint is None

    @pytest.mark.asyncio
    async def test_missing_execution_id_raises(self) -> None:
        with pytest.raises(ValueError, match="execution_id is required"):
            ContextBuilder("", "agent-1")

    @pytest.mark.asyncio
    async def test_missing_agent_id_raises(self) -> None:
        with pytest.raises(ValueError, match="agent_id is required"):
            ContextBuilder("exec-1", "")


class TestContextBuilderOptions:
    @pytest.mark.asyncio
    async def test_with_budget(self) -> None:
        ctx = ContextBuilder("e", "a").with_budget(500).build()
        assert ctx.budget_remaining == 500

    @pytest.mark.asyncio
    async def test_with_step_number(self) -> None:
        ctx = ContextBuilder("e", "a").with_step_number(5).build()
        assert ctx.step_number == 5

    @pytest.mark.asyncio
    async def test_with_state(self) -> None:
        ctx = ContextBuilder("e", "a").with_state({"x": 1}).build()
        assert ctx.state == {"x": 1}

    @pytest.mark.asyncio
    async def test_with_allowed_tools(self) -> None:
        ctx = ContextBuilder("e", "a").with_allowed_tools(["mcp.*"]).build()
        assert ctx.allowed_tools == ["mcp.*"]

    @pytest.mark.asyncio
    async def test_with_memory(self) -> None:
        class FakeRepo:
            pass

        repo = FakeRepo()
        ctx = ContextBuilder("e", "a").with_memory(repo).build()
        assert ctx.memory is repo

    @pytest.mark.asyncio
    async def test_with_checkpoint(self) -> None:
        class FakeRepo:
            pass

        repo = FakeRepo()
        ctx = ContextBuilder("e", "a").with_checkpoint(repo).build()
        assert ctx.checkpoint is repo


class TestContextBuilderIsolation:
    @pytest.mark.asyncio
    async def test_state_deep_copied(self) -> None:
        state = {"nested": {"value": 1}}
        ctx = ContextBuilder("e", "a").with_state(state).build()
        state["nested"]["value"] = 999
        assert ctx.state["nested"]["value"] == 1

    @pytest.mark.asyncio
    async def test_tools_deep_copied(self) -> None:
        tools = ["mcp.*"]
        ctx = ContextBuilder("e", "a").with_allowed_tools(tools).build()
        tools.append("http.*")
        assert ctx.allowed_tools == ["mcp.*"]

    @pytest.mark.asyncio
    async def test_builder_state_mutation_no_affect(self) -> None:
        builder = ContextBuilder("e", "a").with_state({"x": 1})
        ctx1 = builder.build()
        ctx2 = builder.with_state({"x": 2}).build()
        assert ctx1.state == {"x": 1}
        assert ctx2.state == {"x": 2}
