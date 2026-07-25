"""Tests for API authentication layer."""

import pytest

from api.auth.provider import (
    APIKeyAuthProvider,
    AuthContext,
)


class TestAuthContext:
    """Auth context model tests."""

    def test_default_values(self):
        ctx = AuthContext()
        assert ctx.tenant_id == ""
        assert ctx.agent_id == ""
        assert ctx.permissions == []

    def test_custom_values(self):
        ctx = AuthContext(
            tenant_id="t1",
            agent_id="a1",
            permissions=["read", "write"],
        )
        assert ctx.tenant_id == "t1"
        assert ctx.agent_id == "a1"
        assert ctx.permissions == ["read", "write"]


class TestAPIKeyAuthProvider:
    """API key auth provider tests."""

    @pytest.mark.asyncio
    async def test_valid_key_returns_context(self):
        ctx = AuthContext(tenant_id="t1", agent_id="a1")
        provider = APIKeyAuthProvider(keys={"key-123": ctx})

        result = await provider.authenticate("key-123")
        assert result is not None
        assert result.tenant_id == "t1"
        assert result.agent_id == "a1"

    @pytest.mark.asyncio
    async def test_invalid_key_returns_none(self):
        provider = APIKeyAuthProvider(
            keys={"valid-key": AuthContext(tenant_id="t1")}
        )
        result = await provider.authenticate("invalid-key")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_key_returns_none(self):
        provider = APIKeyAuthProvider()
        result = await provider.authenticate("")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_provider_returns_none(self):
        provider = APIKeyAuthProvider()
        result = await provider.authenticate("any-key")
        assert result is None

    @pytest.mark.asyncio
    async def test_multiple_keys(self):
        ctx1 = AuthContext(tenant_id="t1")
        ctx2 = AuthContext(tenant_id="t2")
        provider = APIKeyAuthProvider(keys={"key-1": ctx1, "key-2": ctx2})

        assert (await provider.authenticate("key-1")).tenant_id == "t1"
        assert (await provider.authenticate("key-2")).tenant_id == "t2"

    @pytest.mark.asyncio
    async def test_add_key_dynamically(self):
        provider = APIKeyAuthProvider()
        provider.add_key("key-new", AuthContext(tenant_id="t3"))
        result = await provider.authenticate("key-new")
        assert result is not None
        assert result.tenant_id == "t3"

    @pytest.mark.asyncio
    async def test_authenticate_is_idempotent(self):
        ctx = AuthContext(tenant_id="t1")
        provider = APIKeyAuthProvider(keys={"key": ctx})

        r1 = await provider.authenticate("key")
        r2 = await provider.authenticate("key")
        assert r1 == r2
