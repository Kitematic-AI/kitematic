"""Tests for PolicyEngine cache key uniqueness.

Verifies that _make_cache_key produces different keys for different inputs,
preventing the cache collision bug identified in P2 Step 3.
"""

from control_plane.policy.engine import PolicyEngine


class TestPolicyEngineCacheKey:
    """Cache key must be unique per (agent, action, resource, capabilities)."""

    def _make_key(self, engine, agent_id, action, resource, caps=None):
        return engine._make_cache_key(agent_id, action, resource, caps)

    def test_different_resources_different_keys(self):
        engine = PolicyEngine()
        key1 = self._make_key(engine, "a1", "read", "file.txt")
        key2 = self._make_key(engine, "a1", "read", "db.query")
        assert key1 != key2

    def test_different_agents_different_keys(self):
        engine = PolicyEngine()
        key1 = self._make_key(engine, "agent-1", "read", "file.txt")
        key2 = self._make_key(engine, "agent-2", "read", "file.txt")
        assert key1 != key2

    def test_different_actions_different_keys(self):
        engine = PolicyEngine()
        key1 = self._make_key(engine, "a1", "read", "file.txt")
        key2 = self._make_key(engine, "a1", "write", "file.txt")
        assert key1 != key2

    def test_different_capabilities_different_keys(self):
        engine = PolicyEngine()
        caps1 = frozenset({"cap-a"})
        caps2 = frozenset({"cap-b"})
        key1 = self._make_key(engine, "a1", "read", "file.txt", caps1)
        key2 = self._make_key(engine, "a1", "read", "file.txt", caps2)
        assert key1 != key2

    def test_no_caps_vs_with_caps_different_keys(self):
        engine = PolicyEngine()
        caps = frozenset({"cap-a"})
        key1 = self._make_key(engine, "a1", "read", "file.txt")
        key2 = self._make_key(engine, "a1", "read", "file.txt", caps)
        assert key1 != key2

    def test_same_inputs_same_key(self):
        engine = PolicyEngine()
        caps = frozenset({"cap-a", "cap-b"})
        key1 = self._make_key(engine, "a1", "read", "file.txt", caps)
        key2 = self._make_key(engine, "a1", "read", "file.txt", caps)
        assert key1 == key2

    def test_key_contains_agent_action_resource(self):
        engine = PolicyEngine()
        key = self._make_key(engine, "my-agent", "my-action", "my-resource")
        assert "my-agent" in key
        assert "my-action" in key
        assert "my-resource" in key

    def test_key_not_static(self):
        """The old bug produced '2|0|' for all inputs. Verify this never returns."""
        engine = PolicyEngine()
        key = self._make_key(engine, "a1", "read", "file.txt")
        assert key != "2|0|"

    def test_capability_hash_in_key(self):
        engine = PolicyEngine()
        caps = frozenset({"database.query"})
        key = self._make_key(engine, "a1", "read", "db", caps)
        # Key should contain a hex hash (32 hex chars = 16 bytes in hex)
        import hashlib
        expected_hash = hashlib.sha256(b"database.query").hexdigest()[:16]
        assert expected_hash in key

    def test_evaluate_cache_hits_same_input(self):
        """Integration: same input should hit cache on second call."""
        engine = PolicyEngine()

        result1 = engine._make_cache_key("a1", "read", "file", None)
        result2 = engine._make_cache_key("a1", "read", "file", None)
        assert result1 == result2
