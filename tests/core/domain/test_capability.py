"""Tests for Capability domain model."""

from core.domain.capability import Capability


class TestCapability:
    def test_create_low_risk(self) -> None:
        cap = Capability(name="filesystem.read", risk_level="low")
        assert cap.name == "filesystem.read"
        assert cap.risk_level == "low"
        assert cap.permissions == ()

    def test_create_high_risk(self) -> None:
        cap = Capability(
            name="shell.execute",
            risk_level="critical",
            description="Execute arbitrary shell commands",
            permissions=["shell.execute", "network.http"],
        )
        assert cap.risk_level == "critical"
        assert "shell.execute" in cap.permissions

    def test_create_medium_risk_with_description(self) -> None:
        cap = Capability(
            name="code.generate",
            risk_level="medium",
            description="Generate and write code files",
            permissions=["filesystem.write"],
        )
        assert cap.description == "Generate and write code files"
        assert cap.permissions == ("filesystem.write",)
        assert len(cap.permissions) == 1
