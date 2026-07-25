"""Plugin manifest validation — validates raw YAML/dict against PluginManifest schema."""

from __future__ import annotations

from typing import Any

from core.domain.capability import Capability
from core.domain.plugin import PluginManifest, PluginType


class ValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def validate_manifest(raw: dict[str, Any]) -> PluginManifest:
    """Parse and validate a raw manifest dict.

    Args:
        raw: Parsed manifest dictionary (from YAML or JSON).

    Returns:
        Validated PluginManifest.

    Raises:
        ValidationError: If any required fields are missing or invalid.
    """
    errors: list[str] = []

    name = _require_str(raw, "name", errors)
    version = _require_str(raw, "version", errors)

    plugin_type_raw = raw.get("plugin_type", "")
    try:
        plugin_type = PluginType(plugin_type_raw)
    except ValueError:
        errors.append(f"invalid plugin_type '{plugin_type_raw}'; expected one of {[t.value for t in PluginType]}")
        plugin_type = PluginType.TOOL

    runtime_type = _require_str(raw, "runtime_type", errors)
    description = raw.get("description", "")
    author = _require_str(raw, "author", errors)

    entrypoint = raw.get("entrypoint")
    if not isinstance(entrypoint, dict):
        errors.append("entrypoint must be a dict with 'module' and 'class' keys")
        entrypoint_raw: dict[str, str] = {}
    else:
        entrypoint_raw = entrypoint
        if "module" not in entrypoint_raw:
            errors.append("entrypoint.module is required")
        if "class" not in entrypoint_raw:
            errors.append("entrypoint.class is required")

    capabilities_raw = raw.get("capabilities", [])
    capabilities: list[Capability] = []
    for i, cap in enumerate(capabilities_raw):
        if not isinstance(cap, dict):
            errors.append(f"capabilities[{i}] must be a dict")
            continue
        cap_name = cap.get("name", "")
        if not cap_name:
            errors.append(f"capabilities[{i}].name is required")
        risk = cap.get("risk_level", "low")
        if risk not in ("low", "medium", "high", "critical"):
            errors.append(f"capabilities[{i}].risk_level must be one of low, medium, high, critical")
        perm_list = cap.get("permissions", [])
        if not isinstance(perm_list, list):
            perm_list = []
        capabilities.append(Capability(
            name=cap.get("name", ""),
            risk_level=risk,
            description=cap.get("description", ""),
            permissions=tuple(perm_list),
        ))

    permissions = raw.get("permissions", [])
    if not isinstance(permissions, list):
        errors.append("permissions must be a list")

    dependencies = raw.get("dependencies", [])
    if not isinstance(dependencies, list):
        errors.append("dependencies must be a list")

    min_kernel_version = raw.get("min_kernel_version", "1.0.0")
    config_schema = raw.get("config_schema")
    provider = raw.get("provider")

    if errors:
        raise ValidationError(errors)

    return PluginManifest(
        name=name,
        version=version,
        plugin_type=plugin_type,
        runtime_type=runtime_type,
        description=description,
        author=author,
        entrypoint=entrypoint_raw,
        capabilities=[c.__dict__ for c in capabilities],
        permissions=permissions,
        dependencies=dependencies,
        min_kernel_version=min_kernel_version,
        config_schema=config_schema,
        provider=provider,
    )


def _require_str(raw: dict[str, Any], key: str, errors: list[str]) -> str:
    """Get a required string field or add an error."""
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{key} is required")
        return ""
    return value.strip()
