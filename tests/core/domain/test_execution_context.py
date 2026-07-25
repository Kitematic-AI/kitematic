"""Tests for ExecutionContext."""

from core.domain.capability_binding import CapabilityBinding
from core.domain.execution_context import ExecutionContext


class TestHasPermission:
    def test_allows_when_binding_grants(self) -> None:
        binding = CapabilityBinding(
            plugin_name="test",
            capability_name="filesystem",
            permissions=("filesystem.read",),
        )
        ctx = ExecutionContext(plugin_name="test", bindings=[binding])
        assert ctx.has_permission("filesystem.read") is True

    def test_denies_when_no_binding(self) -> None:
        ctx = ExecutionContext(plugin_name="test", bindings=[])
        assert ctx.has_permission("anything") is False

    def test_denies_when_binding_disabled(self) -> None:
        binding = CapabilityBinding(
            plugin_name="test",
            capability_name="shell",
            permissions=("shell.execute",),
        )
        binding.disable()
        ctx = ExecutionContext(plugin_name="test", bindings=[binding])
        assert ctx.has_permission("shell.execute") is False

    def test_multiple_bindings_union(self) -> None:
        b1 = CapabilityBinding(
            plugin_name="test",
            capability_name="fs",
            permissions=("filesystem.read",),
        )
        b2 = CapabilityBinding(
            plugin_name="test",
            capability_name="net",
            permissions=("network.egress",),
        )
        ctx = ExecutionContext(plugin_name="test", bindings=[b1, b2])
        assert ctx.has_permission("filesystem.read") is True
        assert ctx.has_permission("network.egress") is True
        assert ctx.has_permission("shell.execute") is False


class TestDeniedPermissions:
    def test_returns_empty_when_all_allowed(self) -> None:
        binding = CapabilityBinding(
            plugin_name="test",
            capability_name="fs",
            permissions=("read", "write"),
        )
        ctx = ExecutionContext(plugin_name="test", bindings=[binding])
        assert ctx.denied_permissions({"read", "write"}) == []

    def test_returns_denied_only(self) -> None:
        binding = CapabilityBinding(
            plugin_name="test",
            capability_name="fs",
            permissions=("read",),
        )
        ctx = ExecutionContext(plugin_name="test", bindings=[binding])
        denied = ctx.denied_permissions({"read", "delete"})
        assert denied == ["delete"]


class TestDefaults:
    def test_default_timeout_is_zero(self) -> None:
        ctx = ExecutionContext(plugin_name="test")
        assert ctx.timeout_seconds == 0.0

    def test_default_max_tokens_is_zero(self) -> None:
        ctx = ExecutionContext(plugin_name="test")
        assert ctx.max_tokens == 0

    def test_default_metadata_is_empty(self) -> None:
        ctx = ExecutionContext(plugin_name="test")
        assert ctx.metadata == {}
