"""Tests for PolicyEngineAdapter — ABI PolicyEvaluator → PolicyEngine."""

import pytest

from control_plane.adapters.to_kernel.policy import PolicyEngineAdapter
from kernel.runtime import Intent


class MockPolicyEngine:
    """Mock PolicyEngine for testing."""

    def __init__(self, response: dict | None = None):
        self._default_response = response if response is not None else {"decision": "ALLOW", "reason": None, "matched_rule": None}
        self._calls: list[dict] = []

    async def evaluate(self, agent_id: str, action: str, resource: str, context=None) -> dict:
        self._calls.append({
            "agent_id": agent_id,
            "action": action,
            "resource": resource,
            "context": context,
        })
        return self._default_response


class TestPolicyEngineAdapterEvaluateIntent:
    """Tests for evaluate_intent method."""

    @pytest.mark.asyncio
    async def test_allow_returns_true(self):
        engine = MockPolicyEngine({"decision": "ALLOW", "reason": None, "matched_rule": None})
        adapter = PolicyEngineAdapter(engine)
        intent = Intent(agent_id="agent-1", action="read_file")

        allowed, reason = await adapter.evaluate_intent(intent)

        assert allowed is True
        assert reason is None

    @pytest.mark.asyncio
    async def test_deny_returns_false_with_reason(self):
        engine = MockPolicyEngine({
            "decision": "DENY",
            "reason": "Access denied by policy",
            "matched_rule": "rule-1",
        })
        adapter = PolicyEngineAdapter(engine)
        intent = Intent(agent_id="agent-1", action="delete_file")

        allowed, reason = await adapter.evaluate_intent(intent)

        assert allowed is False
        assert "Access denied by policy" in reason
        assert "rule-1" in reason

    @pytest.mark.asyncio
    async def test_deny_without_rule(self):
        engine = MockPolicyEngine({
            "decision": "DENY",
            "reason": "Not permitted",
            "matched_rule": None,
        })
        adapter = PolicyEngineAdapter(engine)
        intent = Intent(agent_id="agent-1", action="admin_action")

        allowed, reason = await adapter.evaluate_intent(intent)

        assert allowed is False
        assert reason == "Not permitted"

    @pytest.mark.asyncio
    async def test_malformed_result_denies(self):
        engine = MockPolicyEngine({"broken": "result"})
        adapter = PolicyEngineAdapter(engine)
        intent = Intent(agent_id="agent-1", action="test")

        allowed, reason = await adapter.evaluate_intent(intent)

        assert allowed is False
        assert "Malformed" in reason

    @pytest.mark.asyncio
    async def test_empty_result_denies(self):
        engine = MockPolicyEngine({})
        adapter = PolicyEngineAdapter(engine)
        intent = Intent(agent_id="agent-1", action="test")

        allowed, reason = await adapter.evaluate_intent(intent)

        assert allowed is False
        assert "missing decision" in reason

    @pytest.mark.asyncio
    async def test_intent_decomposition(self):
        engine = MockPolicyEngine()
        adapter = PolicyEngineAdapter(engine)
        intent = Intent(
            agent_id="agent-42",
            action="mcp.database.query",
            parameters={"query": "SELECT 1"},
        )

        await adapter.evaluate_intent(intent)

        call = engine._calls[-1]
        assert call["agent_id"] == "agent-42"
        assert call["action"] == "mcp.database.query"
        assert call["resource"] == "mcp.database.query"


class TestPolicyEngineAdapterCheckCapability:
    """Tests for check_capability method."""

    @pytest.mark.asyncio
    async def test_allow_returns_true(self):
        engine = MockPolicyEngine({"decision": "ALLOW", "reason": None, "matched_rule": None})
        adapter = PolicyEngineAdapter(engine)

        allowed, reason = await adapter.check_capability("read", "agent-1")

        assert allowed is True
        assert reason is None

    @pytest.mark.asyncio
    async def test_deny_returns_false(self):
        engine = MockPolicyEngine({
            "decision": "DENY",
            "reason": "Capability not registered",
            "matched_rule": None,
        })
        adapter = PolicyEngineAdapter(engine)

        allowed, reason = await adapter.check_capability("admin", "agent-1")

        assert allowed is False
        assert "Capability not registered" in reason

    @pytest.mark.asyncio
    async def test_check_capability_decomposition(self):
        engine = MockPolicyEngine()
        adapter = PolicyEngineAdapter(engine)

        await adapter.check_capability("write_file", "agent-99")

        call = engine._calls[-1]
        assert call["agent_id"] == "agent-99"
        assert call["action"] == "write_file"
        assert call["resource"] == "write_file"
