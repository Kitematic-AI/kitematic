"""Tests for PluginManifest domain model."""

from core.domain.plugin import PluginManifest, PluginType


class TestPluginManifest:
    def test_create_tool_plugin(self) -> None:
        manifest = PluginManifest(
            name="claude-code",
            version="1.0.0",
            plugin_type=PluginType.TOOL,
            runtime_type="coding-agent",
            description="Claude Code integration",
            author="Anthropic",
            entrypoint={"module": "agents.tools.claude_code.adapter", "class": "ClaudeCodeAdapter"},
        )
        assert manifest.name == "claude-code"
        assert manifest.plugin_type == PluginType.TOOL
        assert manifest.is_valid

    def test_create_agent_plugin(self) -> None:
        manifest = PluginManifest(
            name="financial-agent",
            version="0.2.0",
            plugin_type=PluginType.AGENT,
            runtime_type="autonomous-agent",
            description="Financial analysis agent",
            author="Kitematic Labs",
            entrypoint={"module": "agents.frameworks.financial.adapter", "class": "FinancialAgent"},
        )
        assert manifest.plugin_type == PluginType.AGENT
        assert manifest.is_valid

    def test_create_model_plugin(self) -> None:
        manifest = PluginManifest(
            name="ollama",
            version="1.0.0",
            plugin_type=PluginType.MODEL,
            runtime_type="llm-server",
            description="Local LLM via Ollama",
            author="Ollama",
            entrypoint={"module": "agents.models.ollama.provider", "class": "OllamaProvider"},
        )
        assert manifest.plugin_type == PluginType.MODEL
        assert manifest.is_valid

    def test_create_framework_plugin(self) -> None:
        manifest = PluginManifest(
            name="langgraph",
            version="0.1.0",
            plugin_type=PluginType.FRAMEWORK,
            runtime_type="graph-runtime",
            description="LangGraph agent runtime adapter",
            author="LangChain",
            entrypoint={"module": "agents.frameworks.langgraph.adapter", "class": "LangGraphAdapter"},
        )
        assert manifest.plugin_type == PluginType.FRAMEWORK
        assert manifest.is_valid

    def test_validation_fails_without_required_fields(self) -> None:
        manifest = PluginManifest(
            name="",
            version="",
            plugin_type=PluginType.TOOL,
            runtime_type="",
            description="",
            author="",
            entrypoint={},
        )
        assert not manifest.is_valid
        errors = manifest.validate()
        assert "name is required" in errors
        assert "version is required" in errors
        assert "entrypoint.module is required" in errors
        assert "entrypoint.class is required" in errors
        assert "runtime_type is required" in errors
