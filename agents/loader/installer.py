"""Plugin installer — install, remove, and list plugins.

Handles the filesystem operations for plugin lifecycle.
Supports install from a local path or from a registry URL.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

import yaml

from core.domain.plugin import PluginManifest
from agents.loader.discovery import PLUGIN_DIRS, discover_plugins
from agents.loader.validator import ValidationError, validate_manifest

logger = logging.getLogger("kitematic.loader.installer")


def install_from_path(source: Path, root: Path | None = None) -> PluginManifest:
    """Install a plugin from a local directory.

    The source directory must contain a valid manifest.yaml.

    Args:
        source: Path to the plugin directory.
        root: Project root (auto-detected if None).

    Returns:
        The installed PluginManifest.

    Raises:
        ValidationError: If the manifest is invalid.
        OSError: If filesystem operations fail.
    """
    if root is None:
        from agents.loader.discovery import _find_project_root
        root = _find_project_root()

    manifest_file = source / "manifest.yaml"
    if not manifest_file.is_file():
        raise ValidationError([f"manifest.yaml not found in {source}"])

    with open(manifest_file) as f:
        raw: dict[str, Any] = yaml.safe_load(f)

    manifest = validate_manifest(raw)
    dest = _plugin_dest(root, manifest)

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest, dirs_exist_ok=True)
    logger.info("Installed plugin '%s' v%s from %s", manifest.name, manifest.version, source)
    return manifest


def install_from_registry(name: str, version: str | None = None) -> PluginManifest:
    """Install a plugin from the marketplace registry.

    Args:
        name: Plugin name to look up in the registry.
        version: Semantic version constraint (None = latest).

    Returns:
        The installed PluginManifest.

    Raises:
        NotImplementedError: Registry is not yet implemented.
    """
    raise NotImplementedError("Registry-based install is not yet implemented")


def remove(name: str, root: Path | None = None) -> bool:
    """Remove an installed plugin by name.

    Args:
        name: Plugin name.
        root: Project root.

    Returns:
        True if the plugin was removed, False if not found.
    """
    if root is None:
        from agents.loader.discovery import _find_project_root
        root = _find_project_root()

    manifest = discover_plugins(root)
    target = None
    for m in manifest:
        if m.name == name:
            target = m
            break

    if target is None:
        logger.warning("Plugin '%s' not found", name)
        return False

    dest = _plugin_dest(root, target)
    if dest.is_dir():
        shutil.rmtree(dest)
        logger.info("Removed plugin '%s' v%s", name, target.version)
        return True
    return False


def list_installed(root: Path | None = None) -> list[PluginManifest]:
    """List all installed plugins.

    Args:
        root: Project root.

    Returns:
        List of validated PluginManifests.
    """
    return discover_plugins(root)


def _plugin_dest(root: Path, manifest: PluginManifest) -> Path:
    """Compute the installation directory for a plugin based on its type."""
    type_dir = manifest.plugin_type.value + "s"
    if type_dir == "agents":
        type_dir = "tools"
    return root / "agents" / type_dir / manifest.name
