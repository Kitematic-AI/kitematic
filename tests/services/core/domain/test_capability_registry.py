"""Tests for CapabilityRegistry and CapabilityCatalog."""


from control_plane.policy.resolver import CapabilityResolver
from core.policies.capability import Capability, CapabilityCategory
from core.policies.capability_catalog import CapabilityCatalog
from core.policies.capability_registry import CapabilityRegistry


class TestCapabilityRegistry:
    """Tests for CapabilityRegistry."""

    def test_register_and_get(self):
        """Test registering and retrieving a capability."""
        cap = Capability(
            id="test.capability",
            name="Test Capability",
            category="test",
            risk_level="low",
        )
        registry = CapabilityRegistry()
        registry.register(cap)

        retrieved = registry.get("test.capability")
        assert retrieved is not None
        assert retrieved.id == "test.capability"
        assert retrieved.name == "Test Capability"

    def test_contains(self):
        """Test checking if a capability is registered."""
        cap = Capability(id="test.cap", name="Test", category="tool")
        registry = CapabilityRegistry()
        registry.register(cap)

        assert registry.contains("test.cap")
        assert not registry.contains("nonexistent")

    def test_list(self):
        """Test listing all registered capabilities."""
        cap1 = Capability(id="cap1", name="Cap 1", category="tool")
        cap2 = Capability(id="cap2", name="Cap 2", category="tool")
        registry = CapabilityRegistry((cap1, cap2))

        caps = registry.list()
        assert len(caps) == 2
        assert all(isinstance(c, Capability) for c in caps)

    def test_remove(self):
        """Test removing a capability."""
        cap = Capability(id="test.cap", name="Test", category="test")
        registry = CapabilityRegistry()
        registry.register(cap)

        registry.remove("test.capability")
        assert not registry.contains("test.capability")
        assert registry.get("test.capability") is None

    def test_count(self):
        """Test counting registered capabilities."""
        registry = CapabilityRegistry()
        assert registry.count() == 0

        registry.register(Capability(id="a", name="A", category="test"))
        assert registry.count() == 1

        registry.register(Capability(id="b", name="B", category="test"))
        assert registry.count() == 2

    def test_query_by_category(self):
        """Test querying capabilities by category."""
        registry = CapabilityRegistry((
            Capability(id="model.cap", name="Model Cap", category="model", risk_level="low"),
            Capability(id="tool.exec", name="Tool Exec", category="tool", risk_level="medium"),
            Capability(id="data.read", name="Data Read", category="data", risk_level="low"),
        )
        )

        model_caps = registry.query(category="model")
        assert len(model_caps) == 1
        assert model_caps[0].id == "model.cap"

    def test_query_by_risk_level(self):
        """Test querying capabilities by risk level."""
        registry = CapabilityRegistry((
            Capability(id="low.risk", name="Low Risk", category="test", risk_level="low"),
            Capability(id="high.risk", name="High Risk", category="test", risk_level="high"),
        ))

        low_risk = registry.query(risk_level="low")
        assert len(low_risk) == 1
        assert low_risk[0].id == "low.risk"

    def test_get_compatible_exact_match(self):
        """Test getting compatible capabilities with exact match."""
        from core.policies.capability import Capability

        registry = CapabilityRegistry()
        registry.register(Capability(id="test.cap", name="Test", category="tool", version="1.0.0"))

        compatible = registry.get_compatible("test.cap")
        assert len(compatible) == 1
        assert compatible[0].id == "test.cap"

    def test_get_compatible_exact_version_match(self):
        """Test getting compatible capabilities with exact version match."""
        from core.policies.capability import Capability

        registry = CapabilityRegistry()
        registry.register(Capability(id="test.cap", name="Test", category="tool", version="1.0.0"))

        # Exact version match
        compatible = registry.get_compatible("test.cap", version_constraint="1.0.0")
        assert len(compatible) == 1

        # Non-matching version
        no_match = registry.get_compatible("test.cap", version_constraint="2.0.0")
        assert len(no_match) == 0


class TestCapabilityCatalog:
    """Tests for CapabilityCatalog."""

    def test_all_returns_all_capabilities(self):
        """Test that all() returns all built-in capabilities."""
        capabilities = CapabilityCatalog.all()
        assert len(capabilities) == 16  # Based on our catalog

    def test_by_id(self):
        """Test looking up capability by ID."""
        cap = CapabilityCatalog.by_id("chat.generate")
        assert cap is not None
        assert cap.id == "chat.generate"
        assert cap.name == "Chat Generation"

    def test_by_id_not_found(self):
        """Test lookup of non-existent capability returns None."""
        cap = CapabilityCatalog.by_id("nonexistent.capability")
        assert cap is None

    def test_all_returns_correct_count(self):
        """Test that all() returns the expected number of capabilities."""
        capabilities = CapabilityCatalog.all()
        assert len(capabilities) == 16  # 16 built-in capabilities

    def test_resolve_version_exact_match(self):
        """Test resolving capability with exact version match."""
        cap = CapabilityCatalog.resolve_version("chat.generate", "1.0")
        assert cap is not None
        assert cap.id == "chat.generate"

    def test_resolve_version_mismatch(self):
        """Test that version mismatch returns None."""
        cap = CapabilityCatalog.resolve_version("chat.generate", "2.0")
        assert cap is None

    def test_resolve_version_no_constraint(self):
        """Test resolving without version constraint returns capability."""
        cap = CapabilityCatalog.resolve_version("chat.generate")
        assert cap is not None
        assert cap.id == "chat.generate"

    def test_by_id_not_found_returns_none(self):
        """Test that by_id returns None for unknown IDs."""
        cap = CapabilityCatalog.by_id("nonexistent")
        assert cap is None

    def test_all_capabilities_have_required_fields(self):
        """Test that all capabilities have required fields populated."""
        for cap in CapabilityCatalog.all():
            assert cap.id
            assert cap.name
            assert cap.category
            assert cap.risk_level in ("low", "medium", "high", "critical")
            assert cap.version == "1.0"  # Default version
            assert cap.description


class TestCapabilityCatalogCompatibility:
    """Tests for capability compatibility resolution."""

    def test_get_compatible_exact_match(self):
        """Test getting compatible capabilities with exact match."""
        from core.policies.capability_catalog import CapabilityCatalog

        compatible = CapabilityCatalog.get_compatible("chat.generate")
        assert len(compatible) == 1
        assert compatible[0].id == "chat.generate"

    def test_get_compatible_with_version_constraint(self):
        """Test getting compatible capabilities with version constraint."""
        from core.policies.capability_catalog import CapabilityCatalog

        compatible = CapabilityCatalog.get_compatible("chat.generate", version_constraint="1.0")
        assert len(compatible) == 1
        assert compatible[0].id == "chat.generate"

    def test_get_compatible_version_mismatch(self):
        """Test that version mismatch returns empty tuple."""
        from core.policies.capability_catalog import CapabilityCatalog

        compatible = CapabilityCatalog.get_compatible("chat.generate", version_constraint="2.0")
        assert len(compatible) == 0

    def test_get_compatible_no_version_constraint(self):
        """Test getting compatible without version constraint."""
        from core.policies.capability_catalog import CapabilityCatalog

        compatible = CapabilityCatalog.get_compatible("chat.generate")
        assert len(compatible) == 1
        assert compatible[0].id == "chat.generate"


class TestCapabilityResolver:
    """Tests for CapabilityResolver."""

    def test_validate_required_all_present(self):
        """Test validation when all required capabilities are present."""
        from core.policies.capability_catalog import CapabilityCatalog
        from core.policies.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry(CapabilityCatalog.all())
        resolver = CapabilityResolver(CapabilityRegistry(CapabilityCatalog.all()))

        result = resolver.validate_required(frozenset(["chat.generate", "tool.execute"]))
        assert result.valid is True
        assert result.missing == ()

    def test_validate_required_missing(self):
        """Test validation when some capabilities are missing."""
        from core.policies.capability_catalog import CapabilityCatalog
        from core.policies.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry(CapabilityCatalog.all())
        resolver = CapabilityResolver(CapabilityRegistry(CapabilityCatalog.all()))

        result = resolver.validate_required(frozenset(["chat.generate", "nonexistent.cap"]))
        assert result.valid is False
        assert "nonexistent.cap" in result.missing

    def test_resolve_returns_registered_capabilities(self):
        """Test that resolve returns registered capabilities."""
        from core.policies.capability_catalog import CapabilityCatalog
        from core.policies.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry(CapabilityCatalog.all())
        resolver = CapabilityResolver(CapabilityRegistry(CapabilityCatalog.all()))

        resolved = resolver.resolve(frozenset(["chat.generate", "tool.execute"]))
        assert len(resolved) == 2
        assert all(hasattr(c, 'id') for c in resolved)

    def test_is_registered(self):
        """Test checking if a capability is registered."""
        from core.policies.capability_catalog import CapabilityCatalog
        from core.policies.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry(CapabilityCatalog.all())
        resolver = CapabilityResolver(CapabilityRegistry(CapabilityCatalog.all()))

        assert resolver.is_registered("chat.generate") is True
        assert resolver.is_registered("nonexistent.cap") is False


class TestCapabilityRegistryQueries:
    """Tests for CapabilityRegistry query methods."""

    def test_query_by_category(self):
        """Test querying capabilities by category."""
        from core.policies.capability import Capability
        from core.policies.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry((
            Capability(id="model.cap", name="Model", category=CapabilityCategory.MODEL),
            Capability(id="tool.cap", name="Tool", category=CapabilityCategory.TOOL),
        ))

        model_caps = registry.query(category=CapabilityCategory.MODEL)
        assert len(model_caps) == 1
        assert model_caps[0].id == "model.cap"

    def test_query_by_risk_level(self):
        from core.policies.capability import Capability
        from core.policies.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry((
            Capability(id="low.risk", name="Low", category=CapabilityCategory.TOOL, risk_level="low"),
            Capability(id="high.risk", name="High", category=CapabilityCategory.MODEL, risk_level="high"),
        ))

        low = registry.query(risk_level="low")
        assert len(low) == 1
        assert low[0].id == "low.risk"
