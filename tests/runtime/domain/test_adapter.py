"""Tests for Adapter domain model."""

from runtime.domain.adapter import Adapter, AdapterType, TrustLevel


class TestAdapter:
    def test_valid_adapter_passes_validation(self) -> None:
        adapter = Adapter(
            adapter_id="adp-1",
            name="langgraph-runtime",
            type=AdapterType.FRAMEWORK,
            provider="langchain",
            version="2.0",
            trust_level=TrustLevel.T2_TESTED,
            capabilities=("state_machine", "tool_interception"),
        )
        errors = adapter.validate()
        assert len(errors) == 0
        assert adapter.is_valid is True

    def test_missing_required_fields_fails(self) -> None:
        adapter = Adapter(
            adapter_id="",
            name="",
            type=AdapterType.MODEL,
            provider="openai",
            version="1.0",
            trust_level=TrustLevel.T0_UNKNOWN,
        )
        errors = adapter.validate()
        assert len(errors) >= 2

    def test_trust_level_threshold(self) -> None:
        t0 = Adapter(
            adapter_id="a1", name="unknown",
            type=AdapterType.TOOL, provider="x", version="1",
            trust_level=TrustLevel.T0_UNKNOWN,
        )
        t2 = Adapter(
            adapter_id="a2", name="tested",
            type=AdapterType.TOOL, provider="x", version="1",
            trust_level=TrustLevel.T2_TESTED,
        )
        assert t0.is_trusted is False
        assert t2.is_trusted is True
