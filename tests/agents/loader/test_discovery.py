"""Tests for plugin discovery."""

from pathlib import Path

import pytest
import yaml

from agents.loader.discovery import discover_plugins, discover_plugin
from core.domain.plugin import PluginType


def _create_mock_plugin(base: Path, subdir: str, name: str, **overrides: str) -> Path:
    """Create a mock plugin directory with manifest.yaml."""
    plugin_dir = base / "agents" / subdir / name
    plugin_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": name,
        "version": overrides.get("version", "1.0.0"),
        "plugin_type": overrides.get("plugin_type", "tool"),
        "runtime_type": overrides.get("runtime_type", "test-runtime"),
        "description": overrides.get("description", "Test plugin"),
        "author": overrides.get("author", "Test Author"),
        "entrypoint": {
            "module": f"agents.{subdir}.{name}.adapter",
            "class": f"{name.title().replace('-', '')}Adapter",
        },
    }
    with open(plugin_dir / "manifest.yaml", "w") as f:
        yaml.dump(manifest, f)
    return plugin_dir


class TestDiscoverPlugins:
    def test_discover_no_plugins(self, tmp_path: Path) -> None:
        plugins = discover_plugins(tmp_path)
        assert plugins == []

    def test_discover_single_tool(self, tmp_path: Path) -> None:
        _create_mock_plugin(tmp_path, "tools", "claude-code")
        (tmp_path / "agents" / "tools" / "claude-code" / "adapter.py").touch()
        plugins = discover_plugins(tmp_path)
        assert len(plugins) == 1
        assert plugins[0].name == "claude-code"
        assert plugins[0].plugin_type == PluginType.TOOL

    def test_discover_multiple_types(self, tmp_path: Path) -> None:
        _create_mock_plugin(tmp_path, "tools", "claude-code")
        _create_mock_plugin(tmp_path, "frameworks", "langgraph", plugin_type="framework")
        _create_mock_plugin(tmp_path, "models", "ollama", plugin_type="model")
        plugins = discover_plugins(tmp_path)
        assert len(plugins) == 3
        types = {p.plugin_type for p in plugins}
        assert types == {PluginType.TOOL, PluginType.FRAMEWORK, PluginType.MODEL}

    def test_skip_directories_without_manifest(self, tmp_path: Path) -> None:
        (tmp_path / "agents" / "tools" / "empty-dir").mkdir(parents=True)
        plugins = discover_plugins(tmp_path)
        assert plugins == []

    def test_skip_non_directory_entries(self, tmp_path: Path) -> None:
        (tmp_path / "agents" / "tools").mkdir(parents=True)
        (tmp_path / "agents" / "tools" / "not-a-dir.py").touch()
        plugins = discover_plugins(tmp_path)
        assert plugins == []

    def test_skip_invalid_manifest(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        plugin_dir = _create_mock_plugin(tmp_path, "tools", "broken")
        # Overwrite with invalid YAML
        with open(plugin_dir / "manifest.yaml", "w") as f:
            f.write("not: yaml: :broken")
        plugins = discover_plugins(tmp_path)
        assert plugins == []


class TestDiscoverPlugin:
    def test_find_by_name(self, tmp_path: Path) -> None:
        _create_mock_plugin(tmp_path, "tools", "claude-code")
        manifest = discover_plugin("claude-code", tmp_path)
        assert manifest is not None
        assert manifest.name == "claude-code"

    def test_not_found(self, tmp_path: Path) -> None:
        manifest = discover_plugin("non-existent", tmp_path)
        assert manifest is None

    def test_returns_first_match(self, tmp_path: Path) -> None:
        _create_mock_plugin(tmp_path, "tools", "test-plugin")
        _create_mock_plugin(tmp_path, "frameworks", "test-plugin", plugin_type="framework")
        manifest = discover_plugin("test-plugin", tmp_path)
        assert manifest is not None
        # Should return the first one found
        assert manifest.name == "test-plugin"
