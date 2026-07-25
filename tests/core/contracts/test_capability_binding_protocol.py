"""Tests for CapabilityBindingProtocol."""

from core.contracts.capability import CapabilityBindingProtocol
from core.domain.capability_binding import CapabilityBinding


class TestCapabilityBindingProtocol:
    def test_protocol_exists(self) -> None:
        assert CapabilityBindingProtocol is not None

    def test_conforming_binding_passes_isinstance(self) -> None:
        binding = CapabilityBinding(
            plugin_name="test",
            capability_name="filesystem",
            permissions=("read",),
        )
        assert isinstance(binding, CapabilityBindingProtocol)

    def test_non_conforming_class_fails_isinstance(self) -> None:
        class NotABinding:
            pass

        assert not isinstance(NotABinding(), CapabilityBindingProtocol)

    def test_can_execute_via_protocol(self) -> None:
        binding: CapabilityBindingProtocol = CapabilityBinding(
            plugin_name="test",
            capability_name="filesystem",
            permissions=("filesystem.read",),
        )
        assert binding.can_execute("filesystem.read") is True
        assert binding.can_execute("network.egress") is False

    def test_validate_permissions_via_protocol(self) -> None:
        binding: CapabilityBindingProtocol = CapabilityBinding(
            plugin_name="test",
            capability_name="shell",
            permissions=("shell.execute",),
        )
        denied = binding.validate_permissions({"shell.execute", "shell.script"})
        assert denied == ["shell.script"]
