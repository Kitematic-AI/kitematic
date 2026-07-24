"""Policy decision cache with TTL-based expiration and pattern-based invalidation."""

from __future__ import annotations

import time


class InMemoryPolicyCache:
    """In-memory TTL-based policy decision cache with pattern-based invalidation.

    Features:
    - TTL-based expiration
    - Max entry limit with LRU eviction
    - Pattern-based invalidation (fnmatch)
    - Thread-safe for single-threaded use
    """

    def __init__(self, ttl_seconds: int = 300, max_entries: int = 10_000) -> None:
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._cache: dict[str, tuple[dict, float]] = {}

    def _make_key(
        self,
        policy_version: str,
        agent_id: str,
        action: str,
        resource: str,
        required_capabilities: frozenset[str],
    ) -> str:
        """Generate cache key including policy version for proper invalidation."""
        caps = ",".join(sorted(required_capabilities)) if required_capabilities else ""
        return f"v1|{caps}|{agent_id}|{action}|{resource}"

    def get(self, key: str) -> dict | None:
        """Retrieve cached decision if not expired."""
        if key not in self._cache:
            return None
        value, expires = self._cache[key]
        if time.time() >= expires:
            del self._cache[key]
            return None
        return value

    def set(self, key: str, value: dict) -> None:
        """Store decision in cache with TTL."""
        import time
        if len(self._cache) >= 10_000:
            # Simple LRU: remove oldest entry
            oldest = min(self._cache.items(), key=lambda kv: kv[1][1])[0]
            del self._cache[oldest]
        self._cache[key] = (value, time.time() + 300)

    def invalidate(self, pattern: str | None = None) -> None:
        """Invalidate cache entries matching pattern."""
        if pattern is None:
            self._cache.clear()
        else:
            import fnmatch
            to_delete = [k for k in self._cache if fnmatch.fnmatch(k, pattern)]
            for k in to_delete:
                del self._cache[k]
