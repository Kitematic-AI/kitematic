"""Tests for manifest validator."""

import pytest

from agents.loader.validator import ValidationError, validate_manifest
from core.domain.plugin import PluginType


class TestValidateManifest:
    def test_valid_tool_manifest(self) -> None:
        raw = {
            "name": "claude-code",
            "version": "1.0.0",
            "plugin_type": "tool",
            "runtime_type": "coding-agent",
            "description": "Claude Code integration",
            "author": "Anthropic",
            "entrypoint": {
                "module": "agents.tools.claude_code.adapter",
                "class": "ClaudeCodeAdapter",
            },
            "capabilities": [
                {"name": "code.generate", "risk_level": "medium", "permissions": ["filesystem.write"]},
            ],
            "permissions": ["filesystem.write", "filesystem.read"],
            "dependencies": ["anthropic-sdk>=0.30"],
            "min_kernel_version": "1.0.0",
        }
        manifest = validate_manifest(raw)
        assert manifest.name == "claude-code"
        assert manifest.plugin_type == PluginType.TOOL
        assert manifest.is_valid

    def test_valid_model_manifest(self) -> None:
        raw = {
            "name": "ollama",
            "version": "0.1.0",
            "plugin_type": "model",
            "runtime_type": "llm-server",
            "description": "Local LLM via Ollama",
            "author": "Ollama",
            "entrypoint": {
                "module": "agents.models.ollama.provider",
                "class": "OllamaProvider",
            },
        }
        manifest = validate_manifest(raw)
        assert manifest.plugin_type == PluginType.MODEL
        assert manifest.is_valid

    def test_valid_framework_manifest(self) -> None:
        raw = {
            "name": "langgraph",
            "version": "0.1.0",
            "plugin_type": "framework",
            "runtime_type": "graph-runtime",
            "description": "LangGraph agent runtime",
            "author": "LangChain",
            "entrypoint": {
                "module": "agents.frameworks.langgraph.adapter",
                "class": "LangGraphAdapter",
            },
        }
        manifest = validate_manifest(raw)
        assert manifest.plugin_type == PluginType.FRAMEWORK
        assert manifest.is_valid

    def test_valid_agent_manifest(self) -> None:
        raw = {
            "name": "research-agent",
            "version": "2.0.0",
            "plugin_type": "agent",
            "runtime_type": "autonomous-agent",
            "description": "Research agent",
            "author": "Kitematic Labs",
            "entrypoint": {
                "module": "agents.tools.research.adapter",
                "class": "ResearchAdapter",
            },
        }
        manifest = validate_manifest(raw)
        assert manifest.plugin_type == PluginType.AGENT
        assert manifest.is_valid

    def test_missing_required_fields_raises_error(self) -> None:
        raw = {
            "plugin_type": "tool",
            "entrypoint": {},
        }
        with pytest.raises(ValidationError) as exc:
            validate_manifest(raw)
        errors = exc.value.errors
        assert "name is required" in errors
        assert "version is required" in errors
        assert "author is required" in errors
        assert "runtime_type is required" in errors
        assert "entrypoint.module is required" in errors
        assert "entrypoint.class is required" in errors

    def test_invalid_plugin_type_fallback(self) -> None:
        raw = {
            "name": "test",
            "version": "1.0.0",
            "plugin_type": "unknown_type",
            "runtime_type": "test",
            "author": "test",
            "entrypoint": {"module": "test", "class": "Test"},
        }
        with pytest.raises(ValidationError) as exc:
            validate_manifest(raw)
        assert any("invalid plugin_type" in e for e in exc.value.errors)

    def test_invalid_risk_level(self) -> None:
        raw = {
            "name": "test",
            "version": "1.0.0",
            "plugin_type": "tool",
            "runtime_type": "test",
            "author": "test",
            "entrypoint": {"module": "test", "class": "Test"},
            "capabilities": [
                {"name": "danger.zone", "risk_level": "extreme"},
            ],
        }
        with pytest.raises(ValidationError) as exc:
            validate_manifest(raw)
        assert any("risk_level must be" in e for e in exc.value.errors)

    def test_capability_without_name(self) -> None:
        raw = {
            "name": "test",
            "version": "1.0.0",
            "plugin_type": "tool",
            "runtime_type": "test",
            "author": "test",
            "entrypoint": {"module": "test", "class": "Test"},
            "capabilities": [
                {"risk_level": "high"},
            ],
        }
        with pytest.raises(ValidationError) as exc:
            validate_manifest(raw)
        assert any("capabilities[0].name is required" in e for e in exc.value.errors)
