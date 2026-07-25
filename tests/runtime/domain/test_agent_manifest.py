"""Tests for AgentManifest domain model."""

from core.domain.agent_manifest import (
    AgentIdentity,
    AgentManifest,
    AgentStatus,
    Capabilities,
    Constraints,
    RuntimeDefinition,
)


class TestAgentManifest:
    def test_valid_manifest_passes_validation(self) -> None:
        manifest = AgentManifest(
            agent_id="agent-123",
            version="1.0",
            tenant_id="tenant-abc",
            identity=AgentIdentity(
                name="sales-assistant",
                role="sales",
                goal="Help with sales data",
            ),
            runtime_definition=RuntimeDefinition(
                framework="langgraph",
                entrypoint="graph.py",
            ),
            capabilities=Capabilities(
                allowed_tools=("salesforce.read",),
                allowed_models=("gpt-4",),
            ),
            constraints=Constraints(
                max_budget_usd=5.0,
                max_loops=50,
            ),
            policy_profile="pol-default",
        )

        errors = manifest.validate()
        assert len(errors) == 0
        assert manifest.is_valid is True

    def test_missing_required_fields_fails_validation(self) -> None:
        manifest = AgentManifest(
            agent_id="",
            version="",
            tenant_id="",
            identity=AgentIdentity(name="", role="", goal=""),
            runtime_definition=RuntimeDefinition(framework="", entrypoint=""),
            capabilities=Capabilities(),
            constraints=Constraints(),
            policy_profile="",
        )

        errors = manifest.validate()
        assert len(errors) >= 5  # agent_id, version, tenant_id, name, framework
        assert manifest.is_valid is False

    def test_negative_budget_fails_validation(self) -> None:
        manifest = AgentManifest(
            agent_id="agent-123",
            version="1.0",
            tenant_id="tenant-abc",
            identity=AgentIdentity(
                name="test-agent", role="test", goal="testing"
            ),
            runtime_definition=RuntimeDefinition(
                framework="langgraph", entrypoint="graph.py"
            ),
            capabilities=Capabilities(),
            constraints=Constraints(max_budget_usd=-1.0),
            policy_profile="pol-default",
        )

        errors = manifest.validate()
        assert any("budget" in e for e in errors)

    def test_zero_loops_fails_validation(self) -> None:
        manifest = AgentManifest(
            agent_id="agent-123",
            version="1.0",
            tenant_id="tenant-abc",
            identity=AgentIdentity(
                name="test-agent", role="test", goal="testing"
            ),
            runtime_definition=RuntimeDefinition(
                framework="langgraph", entrypoint="graph.py"
            ),
            capabilities=Capabilities(),
            constraints=Constraints(max_loops=0),
            policy_profile="pol-default",
        )

        errors = manifest.validate()
        assert any("loops" in e for e in errors)

    def test_enum_values(self) -> None:
        assert AgentStatus.DRAFT.value == "DRAFT"
        assert AgentStatus.ACTIVE.value == "ACTIVE"
        assert AgentStatus.ARCHIVED.value == "ARCHIVED"
