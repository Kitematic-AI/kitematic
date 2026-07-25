"""Tests for ToolRegistry — tool discovery and validation.

Verifies:
  - ToolDefinition creation and validation
  - Tool registration and retrieval
  - Pattern matching
  - Capability validation
  - Error handling
  - Serialization
"""

import pytest

from kernel.resources.tool_registry import (
    ToolAlreadyRegisteredError,
    ToolCapabilityMismatchError,
    ToolDefinition,
    ToolNotFoundError,
    ToolRegistry,
)

# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def registry():
    return ToolRegistry()


@pytest.fixture
def db_query_tool():
    return ToolDefinition(
        tool_id="mcp.database.query",
        mcp_server="sqlite-server",
        description="Query the database",
    )


@pytest.fixture
def db_write_tool():
    return ToolDefinition(
        tool_id="mcp.database.write",
        mcp_server="sqlite-server",
        description="Write to the database",
        required_capabilities=frozenset(["db_write"]),
    )


@pytest.fixture
def file_read_tool():
    return ToolDefinition(
        tool_id="mcp.file.read",
        mcp_server="file-server",
        description="Read a file",
    )


# ── ToolDefinition Tests ────────────────────────────────────────────────


class TestToolDefinition:
    def test_create_valid_tool(self):
        tool = ToolDefinition(tool_id="t1", mcp_server="s1")
        assert tool.tool_id == "t1"
        assert tool.mcp_server == "s1"
        assert tool.is_valid

    def test_tool_with_description(self):
        tool = ToolDefinition(tool_id="t1", mcp_server="s1", description="desc")
        assert tool.description == "desc"

    def test_tool_with_capabilities(self):
        caps = frozenset(["read", "write"])
        tool = ToolDefinition(tool_id="t1", mcp_server="s1", required_capabilities=caps)
        assert "read" in tool.required_capabilities

    def test_tool_with_tags(self):
        tags = frozenset(["db", "query"])
        tool = ToolDefinition(tool_id="t1", mcp_server="s1", tags=tags)
        assert "db" in tool.tags

    def test_tool_invalid_empty_id(self):
        tool = ToolDefinition(tool_id="", mcp_server="s1")
        assert not tool.is_valid
        errors = tool.validate()
        assert any("tool_id" in e for e in errors)

    def test_tool_invalid_empty_server(self):
        tool = ToolDefinition(tool_id="t1", mcp_server="")
        assert not tool.is_valid

    def test_tool_frozen(self):
        tool = ToolDefinition(tool_id="t1", mcp_server="s1")
        with pytest.raises(AttributeError):
            tool.tool_id = "t2"

    def test_tool_to_dict(self):
        tool = ToolDefinition(
            tool_id="t1",
            mcp_server="s1",
            required_capabilities=frozenset(["cap1"]),
        )
        d = tool.to_dict()
        assert d["tool_id"] == "t1"
        assert d["mcp_server"] == "s1"
        assert d["required_capabilities"] == ["cap1"]

    def test_tool_with_schemas(self):
        tool = ToolDefinition(
            tool_id="t1",
            mcp_server="s1",
            input_schema={"type": "object"},
            output_schema={"type": "array"},
        )
        assert tool.input_schema == {"type": "object"}
        assert tool.output_schema == {"type": "array"}


# ── Registration Tests ──────────────────────────────────────────────────


class TestRegistration:
    def test_register_tool(self, registry, db_query_tool):
        registry.register(db_query_tool)
        assert registry.is_registered("mcp.database.query")

    def test_register_invalid_tool_raises(self, registry):
        invalid = ToolDefinition(tool_id="", mcp_server="")
        with pytest.raises(ValueError):
            registry.register(invalid)

    def test_register_duplicate_raises(self, registry, db_query_tool):
        registry.register(db_query_tool)
        with pytest.raises(ToolAlreadyRegisteredError):
            registry.register(db_query_tool)

    def test_unregister_tool(self, registry, db_query_tool):
        registry.register(db_query_tool)
        registry.unregister("mcp.database.query")
        assert not registry.is_registered("mcp.database.query")

    def test_unregister_nonexistent_raises(self, registry):
        with pytest.raises(ToolNotFoundError):
            registry.unregister("nonexistent")

    def test_get_registered_tool(self, registry, db_query_tool):
        registry.register(db_query_tool)
        tool = registry.get("mcp.database.query")
        assert tool is db_query_tool

    def test_get_nonexistent_returns_none(self, registry):
        tool = registry.get("nonexistent")
        assert tool is None

    def test_list_tools(self, registry, db_query_tool, file_read_tool):
        registry.register(db_query_tool)
        registry.register(file_read_tool)
        tools = registry.list_tools()
        assert len(tools) == 2
        ids = {t.tool_id for t in tools}
        assert "mcp.database.query" in ids
        assert "mcp.file.read" in ids

    def test_count(self, registry, db_query_tool):
        assert registry.count == 0
        registry.register(db_query_tool)
        assert registry.count == 1


# ── Pattern Matching Tests ──────────────────────────────────────────────


class TestPatternMatching:
    def test_exact_match(self, registry, db_query_tool):
        registry.register(db_query_tool)
        matches = registry.match_pattern("mcp.database.query")
        assert len(matches) == 1
        assert matches[0].tool_id == "mcp.database.query"

    def test_single_wildcard(self, registry, db_query_tool, db_write_tool):
        registry.register(db_query_tool)
        registry.register(db_write_tool)
        matches = registry.match_pattern("mcp.database.*")
        assert len(matches) == 2

    def test_multi_level_wildcard(self, registry, db_query_tool, file_read_tool):
        registry.register(db_query_tool)
        registry.register(file_read_tool)
        matches = registry.match_pattern("mcp.*")
        assert len(matches) == 2

    def test_no_match(self, registry, db_query_tool):
        registry.register(db_query_tool)
        matches = registry.match_pattern("mcp.file.*")
        assert len(matches) == 0

    def test_partial_match_no_results(self, registry, db_query_tool):
        registry.register(db_query_tool)
        matches = registry.match_pattern("mcp.database.q")
        assert len(matches) == 0


# ── Capability Validation Tests ─────────────────────────────────────────


class TestCapabilityValidation:
    def test_validate_access_success(self, registry, db_query_tool):
        registry.register(db_query_tool)
        tool = registry.validate_access("mcp.database.query")
        assert tool.tool_id == "mcp.database.query"

    def test_validate_access_not_found(self, registry):
        with pytest.raises(ToolNotFoundError):
            registry.validate_access("nonexistent")

    def test_validate_access_no_caps_required(self, registry, db_query_tool):
        registry.register(db_query_tool)
        tool = registry.validate_access("mcp.database.query", frozenset(["anything"]))
        assert tool is not None

    def test_validate_access_caps_match(self, registry, db_write_tool):
        registry.register(db_write_tool)
        tool = registry.validate_access("mcp.database.write", frozenset(["db_write"]))
        assert tool is not None

    def test_validate_access_caps_mismatch(self, registry, db_write_tool):
        registry.register(db_write_tool)
        with pytest.raises(ToolCapabilityMismatchError):
            registry.validate_access("mcp.database.write", frozenset(["read_only"]))

    def test_validate_access_no_caps_provided(self, registry, db_write_tool):
        registry.register(db_write_tool)
        with pytest.raises(ToolCapabilityMismatchError):
            registry.validate_access("mcp.database.write", frozenset())


# ── Serialization Tests ─────────────────────────────────────────────────


class TestSerialization:
    def test_to_dict(self, registry, db_query_tool, file_read_tool):
        registry.register(db_query_tool)
        registry.register(file_read_tool)
        d = registry.to_dict()
        assert d["tool_count"] == 2
        assert "mcp.database.query" in d["tools"]
        assert "mcp.file.read" in d["tools"]
