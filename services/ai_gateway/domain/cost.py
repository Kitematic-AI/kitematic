"""Cost domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Cost:
    """Cost information for a request."""

    amount: float = 0.0
    currency: str = "USD"
    details: dict = None

    def __post_init__(self):
        if self.details is None:
            object.__setattr__(self, "details", {})