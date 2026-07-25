"""Tests for CapabilityBinding."""

from core.domain.capability_binding import CapabilityBinding


class TestCanExecute:
    def test_allows_exact_permission(self) -> None:
        binding = CapabilityBinding(
            plugin_name="test",
            capability_name="filesystem",
            permissions=("filesystem.read", "filesystem.write"),
        )
        assert binding.can_execute("filesystem.read") is True
        assert binding.can_execute("filesystem.write") is True

    def test_denies_unknown_permission(self) -> None:
        binding = CapabilityBinding(
            plugin_name="test",
            capability_name="filesystem",
            permissions=("filesystem.read",),
        )
        assert binding.can_execute("network.egress") is False

    def test_denies_when_disabled(self) -> None:
        binding = CapabilityBinding(
            plugin_name="test",
            capability_name="filesystem",
            permissions=("filesystem.read",),
        )
        binding.disable()
        assert binding.can_execute("filesystem.read") is False


class TestValidatePermissions:
    def test_returns_empty_when_all_allowed(self) -> None:
        binding = CapabilityBinding(
            plugin_name="test",
            capability_name="filesystem",
            permissions=("read", "write", "execute"),
        )
        denied = binding.validate_permissions({"read", "write"})
        assert denied == []

    def test_returns_denied_permissions(self) -> None:
        binding = CapabilityBinding(
            plugin_name="test",
            capability_name="filesystem",
            permissions=("read",),
        )
        denied = binding.validate_permissions({"read", "delete"})
        assert denied == ["delete"]

    def test_returns_all_when_disabled(self) -> None:
        binding = CapabilityBinding(
            plugin_name="test",
            capability_name="shell",
            permissions=("shell.execute",),
        )
        binding.disable()
        denied = binding.validate_permissions({"shell.execute", "shell.script"})
        assert set(denied) == {"shell.execute", "shell.script"}

    def test_empty_request_returns_empty(self) -> None:
        binding = CapabilityBinding(
            plugin_name="test",
            capability_name="filesystem",
        )
        assert binding.validate_permissions(set()) == []


class TestDisable:
    def test_sets_enabled_to_false(self) -> None:
        binding = CapabilityBinding(
            plugin_name="test",
            capability_name="test",
        )
        assert binding.enabled is True
        binding.disable()
        assert binding.enabled is False

    def test_can_be_called_multiple_times(self) -> None:
        binding = CapabilityBinding(
            plugin_name="test",
            capability_name="test",
        )
        binding.disable()
        binding.disable()
        assert binding.enabled is False


class TestScope:
    def test_default_scope_is_none(self) -> None:
        binding = CapabilityBinding(
            plugin_name="test",
            capability_name="test",
        )
        assert binding.scope is None

    def test_custom_scope(self) -> None:
        binding = CapabilityBinding(
            plugin_name="test",
            capability_name="test",
            scope="sandbox",
        )
        assert binding.scope == "sandbox"
