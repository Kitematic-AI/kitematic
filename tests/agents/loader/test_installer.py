"""Tests for plugin installer."""

from pathlib import Path

import pytest
import yaml

from agents.loader.installer import install_from_path, list_installed, remove
from agents.loader.validator import ValidationError


def _create_plugin_source(tmp_path: Path, name: str = "test-plugin") -> Path:
    """Create a plugin source directory with manifest.yaml."""
    plugin_dir = tmp_path / name
    plugin_dir.mkdir(parents=True)
    manifest = {
        "name": name,
        "version": "1.0.0",
        "plugin_type": "tool",
        "runtime_type": "test-runtime",
        "description": "Test plugin",
        "author": "Test Author",
        "entrypoint": {
            "module": f"agents.tools.{name}.adapter",
            "class": f"{name.title().replace('-', '')}Adapter",
        },
    }
    with open(plugin_dir / "manifest.yaml", "w") as f:
        yaml.dump(manifest, f)
    (plugin_dir / "adapter.py").touch()
    return plugin_dir


class TestInstallFromPath:
    def test_install_plugin(self, tmp_path: Path) -> None:
        src = _create_plugin_source(tmp_path, "my-tool")
        dst_root = tmp_path / "plugins"
        result = install_from_path(src, dst_root)
        assert result.name == "my-tool"
        assert (dst_root / "agents" / "tools" / "my-tool" / "manifest.yaml").exists()
        assert (dst_root / "agents" / "tools" / "my-tool" / "adapter.py").exists()

    def test_install_agent_plugin(self, tmp_path: Path) -> None:
        src = _create_plugin_source(tmp_path, "research-agent")
        manifest_path = src / "manifest.yaml"
        with open(manifest_path) as f:
            manifest = yaml.safe_load(f)
        manifest["plugin_type"] = "agent"
        with open(manifest_path, "w") as f:
            yaml.dump(manifest, f)
        dst_root = tmp_path / "plugins"
        result = install_from_path(src, dst_root)
        # Agents are stored alongside tools
        assert (dst_root / "agents" / "tools" / "research-agent" / "manifest.yaml").exists()

    def test_rejects_missing_manifest(self, tmp_path: Path) -> None:
        src = tmp_path / "no-manifest"
        src.mkdir()
        with pytest.raises(ValidationError, match="manifest.yaml not found"):
            install_from_path(src)

    def test_rejects_invalid_manifest(self, tmp_path: Path) -> None:
        src = tmp_path / "bad-plugin"
        src.mkdir()
        with open(src / "manifest.yaml", "w") as f:
            yaml.dump({"name": "bad"}, f)
        with pytest.raises(ValidationError, match="version is required"):
            install_from_path(src)

    def test_overwrite_existing_plugin(self, tmp_path: Path) -> None:
        src = _create_plugin_source(tmp_path, "my-tool")
        dst_root = tmp_path / "plugins"
        install_from_path(src, dst_root)
        result = install_from_path(src, dst_root)
        assert result.name == "my-tool"


class TestRemove:
    def test_remove_existing(self, tmp_path: Path) -> None:
        src = _create_plugin_source(tmp_path, "my-tool")
        dst_root = tmp_path / "plugins"
        install_from_path(src, dst_root)
        remove("my-tool", dst_root)
        assert not (dst_root / "agents" / "tools" / "my-tool").exists()
        assert (dst_root / "agents" / "tools").exists()

    def test_remove_nonexistent_does_not_raise(self, tmp_path: Path) -> None:
        remove("nonexistent", tmp_path)

    def test_remove_partial_match_only(self, tmp_path: Path) -> None:
        src1 = _create_plugin_source(tmp_path, "my-tool")
        src2 = tmp_path / "other-tool"
        src2.mkdir()
        manifest = {
            "name": "other-tool",
            "version": "1.0.0",
            "plugin_type": "tool",
            "runtime_type": "test-runtime",
            "description": "Other tool",
            "author": "Test",
            "entrypoint": {"module": "other", "class": "Other"},
        }
        with open(src2 / "manifest.yaml", "w") as f:
            yaml.dump(manifest, f)
        dst_root = tmp_path / "plugins"
        install_from_path(src1, dst_root)
        install_from_path(src2, dst_root)
        remove("my-tool", dst_root)
        assert not (dst_root / "agents" / "tools" / "my-tool").exists()
        assert (dst_root / "agents" / "tools" / "other-tool").exists()


class TestListInstalled:
    def test_empty(self, tmp_path: Path) -> None:
        assert list_installed(tmp_path) == []

    def test_lists_multiple_plugins(self, tmp_path: Path) -> None:
        src1 = _create_plugin_source(tmp_path, "tool-a")
        src2 = _create_plugin_source(tmp_path, "tool-b")
        dst_root = tmp_path / "plugins"
        install_from_path(src1, dst_root)
        install_from_path(src2, dst_root)
        plugins = list_installed(dst_root)
        names = {p.name for p in plugins}
        assert names == {"tool-a", "tool-b"}

    def test_skips_invalid_manifests(self, tmp_path: Path) -> None:
        dst_root = tmp_path / "plugins"
        (dst_root / "agents" / "tools" / "broken").mkdir(parents=True)
        with open(dst_root / "agents" / "tools" / "broken" / "manifest.yaml", "w") as f:
            f.write("bad: yaml: :format")
        plugins = list_installed(dst_root)
        assert plugins == []
