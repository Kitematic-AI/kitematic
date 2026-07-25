"""Authentication context — domain-level identity contract.

AuthContext is a pure domain value object. It carries identity
information through the request lifecycle. It does NOT carry
authorization decisions — those belong to the Policy Engine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


class AuthContext(BaseModel):
    """Resolved authentication context after successful authentication."""

    tenant_id: str = ""
    agent_id: str = ""
    permissions: list[str] = []


class AuthProvider(ABC):
    """Protocol for authentication providers.

    Every provider MUST return None for unauthenticated requests.
    AuthProvider extracts identity only — it does NOT authorize.
    """

    @abstractmethod
    async def authenticate(self, api_key: str) -> AuthContext | None:
        """Validate api_key and return AuthContext.

        Returns None if the key is invalid or unknown.
        """
        ...
