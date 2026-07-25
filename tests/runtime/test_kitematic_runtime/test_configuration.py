"""Tests for RuntimeSettings — configuration defaults, validation, and wiring.

Verifies:
  - Defaults match existing hardcoded values
  - Environment variable overrides work
  - Invalid values (log level, negative numbers) are rejected
  - Settings are immutable during execution
  - Runtime accepts and stores settings
"""


import pytest
from pydantic import ValidationError

from runtime.kitematic_runtime.config.settings import RuntimeSettings
from kernel.runtime import (
    ExecutionPath,
    Intent,
    IntentRouter,
    KitematicRuntime,
    PolicyEvaluator,
    StatePersistence,
    ToolGateway,
    ToolResult,
)


class MockPolicyEvaluator(PolicyEvaluator):
    async def evaluate_intent(self, intent: Intent) -> tuple[bool, str | None]:
        return True, None

    async def check_capability(self, action: str, agent_id: str) -> tuple[bool, str | None]:
        return True, None


class MockIntentRouter(IntentRouter):
    async def route_intent(self, intent: Intent) -> ExecutionPath:
        return ExecutionPath(tool="mock.tool")


class MockToolGateway(ToolGateway):
    async def access_tool(self, path: ExecutionPath, intent: Intent) -> ToolResult:
        return ToolResult(success=True, data={"ok": True})


class MockStatePersistence(StatePersistence):
    async def save(self, execution_id: str, state: dict) -> str:
        return "cp-1"

    async def restore(self, checkpoint_id: str) -> dict:
        return {}


# ═══════════════════════════════════════════════════════════════════════
# 1. Default Values
# ═══════════════════════════════════════════════════════════════════════


class TestRuntimeSettingsDefaults:
    """Verify all default values match existing hardcoded values."""

    def test_defaults_are_correct(self):
        settings = RuntimeSettings()
        # Budget
        assert settings.budget_max_steps == 10
        assert settings.budget_max_tokens == 100_000
        assert settings.budget_timeout_seconds == 3600
        # Tenant
        assert settings.tenant_max_agents == 10
        assert settings.tenant_max_steps_per_agent == 10
        assert settings.tenant_max_tokens_per_agent == 100_000
        assert settings.tenant_max_concurrent_executions == 5
        assert settings.tenant_max_checkpoints == 100
        # Logging
        assert settings.log_level == "INFO"
        assert settings.log_output == "stdout"
        # API
        assert settings.api_title == "Kitematic Runtime API"
        assert settings.api_version == "0.2.0"


# ═══════════════════════════════════════════════════════════════════════
# 2. Environment Variable Override
# ═══════════════════════════════════════════════════════════════════════


class TestRuntimeSettingsEnvVars:
    """Verify env vars override defaults."""

    def test_env_var_override(self, monkeypatch):
        monkeypatch.setenv("KITEMATIC_BUDGET_MAX_STEPS", "20")
        monkeypatch.setenv("KITEMATIC_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("KITEMATIC_API_TITLE", "Custom API")
        settings = RuntimeSettings()
        assert settings.budget_max_steps == 20
        assert settings.log_level == "DEBUG"
        assert settings.api_title == "Custom API"
        # Unchanged defaults
        assert settings.budget_max_tokens == 100_000

    def test_unset_env_uses_default(self):
        settings = RuntimeSettings()
        assert settings.budget_max_steps == 10


# ═══════════════════════════════════════════════════════════════════════
# 3. Validation — log level
# ═══════════════════════════════════════════════════════════════════════


class TestRuntimeSettingsLogLevelValidation:
    """Verify log_level validator rejects invalid values."""

    def test_invalid_log_level_rejected(self):
        with pytest.raises(ValidationError):
            RuntimeSettings(log_level="TRACE")

    def test_invalid_log_level_case_insensitive(self):
        settings = RuntimeSettings(log_level="debug")
        assert settings.log_level == "DEBUG"

    def test_valid_log_levels_accepted(self):
        for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            settings = RuntimeSettings(log_level=level)
            assert settings.log_level == level


# ═══════════════════════════════════════════════════════════════════════
# 4. Validation — numeric bounds
# ═══════════════════════════════════════════════════════════════════════


class TestRuntimeSettingsNumericValidation:
    """Verify Field(gt=0) rejects non-positive values."""

    def test_negative_budget_rejected(self):
        with pytest.raises(ValidationError):
            RuntimeSettings(budget_max_steps=-1)

    def test_zero_budget_rejected(self):
        with pytest.raises(ValidationError):
            RuntimeSettings(budget_max_steps=0)

    def test_negative_timeout_rejected(self):
        with pytest.raises(ValidationError):
            RuntimeSettings(budget_timeout_seconds=-3600)

    def test_negative_tenant_max_rejected(self):
        with pytest.raises(ValidationError):
            RuntimeSettings(tenant_max_agents=0)


# ═══════════════════════════════════════════════════════════════════════
# 5. Immutability
# ═══════════════════════════════════════════════════════════════════════


class TestRuntimeSettingsImmutability:
    """Verify RuntimeSettings is frozen during execution."""

    def test_frozen_cannot_be_modified(self):
        settings = RuntimeSettings()
        with pytest.raises(Exception):
            settings.budget_max_steps = 20

    def test_frozen_cannot_add_attributes(self):
        settings = RuntimeSettings()
        with pytest.raises(Exception):
            settings.nonexistent = "value"


# ═══════════════════════════════════════════════════════════════════════
# 6. Runtime wiring
# ═══════════════════════════════════════════════════════════════════════


class TestRuntimeSettingsWiring:
    """Verify KitematicRuntime accepts and stores settings."""

    @pytest.mark.asyncio
    async def test_settings_passed_to_runtime(self):
        settings = RuntimeSettings(budget_max_steps=42)
        runtime = KitematicRuntime(
            policy=MockPolicyEvaluator(),
            router=MockIntentRouter(),
            gateway=MockToolGateway(),
            persistence=MockStatePersistence(),
            settings=settings,
        )
        assert runtime._settings.budget_max_steps == 42

    @pytest.mark.asyncio
    async def test_settings_default_used_when_none(self):
        runtime = KitematicRuntime(
            policy=MockPolicyEvaluator(),
            router=MockIntentRouter(),
            gateway=MockToolGateway(),
            persistence=MockStatePersistence(),
        )
        assert runtime._settings.budget_max_steps == 10

    @pytest.mark.asyncio
    async def test_runtime_with_custom_settings_executes_normally(self):
        settings = RuntimeSettings(budget_max_steps=5)
        runtime = KitematicRuntime(
            policy=MockPolicyEvaluator(),
            router=MockIntentRouter(),
            gateway=MockToolGateway(),
            persistence=MockStatePersistence(),
            settings=settings,
        )
        result = await runtime.execute_intent(Intent(agent_id="a1", action="test"))
        assert result.success is True
