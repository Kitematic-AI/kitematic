"""Plugin discovery — scans agents/{tools,frameworks,models}/*/manifest.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from core.domain.plugin import PluginManifest
from agents.loader.validator import ValidationError, validate_manifest


PLUGIN_DIRS = ("tools", "frameworks", "models")


def discover_plugins(root: Path | None = None) -> list[PluginManifest]:
    """Scan all plugin directories and return validated manifests.

    Args:
        root: Project root (defaults to auto-detect from cwd).

    Returns:
        List of validated PluginManifests.
    """
    if root is None:
        root = _find_project_root()
    plugins: list[PluginManifest] = []
    errors: list[tuple[Path, str]] = []

    for subdir in PLUGIN_DIRS:
        plugin_dir = root / "agents" / subdir
        if not plugin_dir.is_dir():
            continue
        for plugin_path in sorted(plugin_dir.iterdir()):
            if not plugin_path.is_dir():
                continue
            manifest_file = plugin_path / "manifest.yaml"
            if not manifest_file.is_file():
                continue
            try:
                manifest = _load_manifest(manifest_file)
                plugins.append(manifest)
            except (ValidationError, yaml.YAMLError, OSError) as exc:
                errors.append((manifest_file, str(exc)))

    if errors:
        _log_errors(errors)

    return plugins


def discover_plugin(name: str, root: Path | None = None) -> PluginManifest | None:
    """Discover a single plugin by name.

    Args:
        name: Plugin name (matches manifest.yaml's 'name' field).
        root: Project root.

    Returns:
        PluginManifest if found, None otherwise.
    """
    for manifest in discover_plugins(root):
        if manifest.name == name:
            return manifest
    return None


def _load_manifest(path: Path) -> PluginManifest:
    """Load and validate a single manifest.yaml file."""
    with open(path) as f:
        raw: dict[str, Any] = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ValidationError(["manifest must be a YAML mapping"])
    return validate_manifest(raw)


def _find_project_root() -> Path:
    """Find the project root by walking up from cwd."""
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        if (parent / "core").is_dir() and (parent / "kernel").is_dir():
            return parent
    return cwd


def _log_errors(errors: list[tuple[Path, str]]) -> None:
    """Log discovery errors (placeholder — structured logging later)."""
    for path, msg in errors:
        import logging
        logging.getLogger("kitematic.loader").warning(
            "Skipping plugin %s: %s", path, msg
        )
