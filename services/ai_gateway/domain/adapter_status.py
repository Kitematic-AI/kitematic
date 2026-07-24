"""AI Gateway adapter status enum."""

from __future__ import annotations

from enum import StrEnum


class AdapterStatus(StrEnum):
    UNKNOWN = "unknown"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"
    ERROR = "error"