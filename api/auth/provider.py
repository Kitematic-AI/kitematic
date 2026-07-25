"""Authentication — API-key based auth with secure key storage.

Upgraded in P3 Step 5:
  - API keys are stored as SHA-256 fingerprints, never raw.
  - Constant-time comparison via hmac.compare_digest.
  - Key rotation support via rotate_key().
  - No BCrypt — API keys are high-entropy, SHA-256 fingerprinting
    is sufficient for indexed lookup.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from core.identity.auth_context import AuthContext, AuthProvider


def _fingerprint(raw_key: str) -> str:
    """Compute SHA-256 fingerprint of an API key.

    Uses hashlib.sha256 for deterministic lookup.
    Constant-time comparison is done by the caller via hmac.compare_digest.
    """
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


class APIKeyAuthProvider(AuthProvider):
    """Concrete auth provider: maps API keys to AuthContexts.

    Keys are stored as SHA-256 fingerprints only — raw keys are never
    retained after storage. Lookup and comparison are constant-time.

    Supports optional key_prefix (e.g. 'kmk_live_') for identifying
    key type at a glance.
    """

    def __init__(
        self,
        keys: dict[str, AuthContext] | None = None,
        key_prefix: str = "",
    ) -> None:
        self._key_prefix = key_prefix
        self._fingerprints: dict[str, AuthContext] = {}
        if keys:
            for raw_key, ctx in keys.items():
                self._fingerprints[_fingerprint(raw_key)] = ctx

    def add_key(self, api_key: str, context: AuthContext) -> None:
        """Register an API key with its auth context.

        Stores the SHA-256 fingerprint — the raw key is discarded.
        """
        self._fingerprints[_fingerprint(api_key)] = context

    def remove_key(self, api_key: str) -> bool:
        """Remove a key by its raw value.

        Returns True if the key existed and was removed.
        """
        fp = _fingerprint(api_key)
        if fp in self._fingerprints:
            del self._fingerprints[fp]
            return True
        return False

    def rotate_key(
        self,
        old_key: str,
        new_key: str,
        context: AuthContext | None = None,
        metrics: Any = None,
    ) -> bool:
        """Rotate from old_key to new_key.

        Removes the old key fingerprint and adds the new one.
        If context is provided, updates the auth context.

        Args:
            old_key: Current API key to replace.
            new_key: New API key to register.
            context: Optional new auth context (defaults to existing).
            metrics: Optional MetricsRegistry for tracking rotation.

        Returns True if the old key existed and rotation succeeded.
        """
        old_fp = _fingerprint(old_key)
        existing_ctx = self._fingerprints.get(old_fp)
        if existing_ctx is None:
            return False
        target_ctx = context if context is not None else existing_ctx
        del self._fingerprints[old_fp]
        self._fingerprints[_fingerprint(new_key)] = target_ctx
        if metrics:
            metrics.increment("security.auth.rotation")
        return True

    async def authenticate(self, api_key: str) -> AuthContext | None:
        """Validate api_key against stored fingerprints.

        Uses constant-time comparison for fingerprint lookup.
        Returns None for unknown keys (safe default).
        Returns None for empty keys.
        """
        if not api_key:
            return None
        candidate = _fingerprint(api_key)
        for stored_fp, ctx in self._fingerprints.items():
            if hmac.compare_digest(candidate, stored_fp):
                return ctx
        return None

    @property
    def key_count(self) -> int:
        """Number of registered API keys."""
        return len(self._fingerprints)
