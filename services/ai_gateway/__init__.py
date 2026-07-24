"""AI Gateway root package."""

from __future__ import annotations

from . import domain, interfaces, registry, adapters

__all__ = [
    "domain",
    "interfaces",
    "registry",
    "adapters",
]