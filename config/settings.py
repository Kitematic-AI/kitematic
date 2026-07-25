from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeSettings(BaseSettings):
    """Runtime configuration loaded from environment variables and .env file.

    All defaults match the existing hardcoded values for backward compatibility.
    Configuration is frozen — it CANNOT change during execution.

    Env var prefix: KITEMATIC_
    Example: KITEMATIC_LOG_LEVEL=DEBUG
    """

    model_config = SettingsConfigDict(
        env_prefix="KITEMATIC_",
        env_file=".env",
        frozen=True,
    )

    # ── Budget ────────────────────────────────────────────────

    budget_max_steps: int = Field(default=10, gt=0)
    budget_max_tokens: int = Field(default=100_000, gt=0)
    budget_timeout_seconds: int = Field(default=3600, gt=0)

    # ── Tenant resource defaults ──────────────────────────────

    tenant_max_agents: int = Field(default=10, gt=0)
    tenant_max_steps_per_agent: int = Field(default=10, gt=0)
    tenant_max_tokens_per_agent: int = Field(default=100_000, gt=0)
    tenant_max_concurrent_executions: int = Field(default=5, gt=0)
    tenant_max_checkpoints: int = Field(default=100, gt=0)

    # ── Logging ───────────────────────────────────────────────

    log_level: str = Field(default="INFO")
    log_output: str = Field(default="stdout")

    # ── Events / Pub-Sub ─────────────────────────────────────

    event_backend: str = Field(default="memory")
    redis_url: str = Field(default="")
    event_channel_prefix: str = Field(default="kitematic")

    # ── Multi-tenant Quotas ───────────────────────────────────

    quota_max_concurrent: int = Field(default=5, ge=0)
    quota_max_per_minute: int = Field(default=60, ge=0)
    quota_max_steps: int = Field(default=10, ge=0)
    quota_rate_limit_per_second: float = Field(default=10.0, ge=0)
    quota_burst_size: int = Field(default=100, ge=0)

    # ── API ───────────────────────────────────────────────────

    api_title: str = Field(default="Kitematic Runtime API")
    api_version: str = Field(default="0.2.0")

    @field_validator("event_backend")
    @classmethod
    def validate_event_backend(cls, value: str) -> str:
        allowed = {"memory", "redis", "redis_pubsub", "redis_streams", "streams"}
        lower = value.lower()
        if lower not in allowed:
            raise ValueError(
                f"Invalid event_backend: {value!r}. Must be one of: {sorted(allowed)}"
            )
        return lower

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = value.upper()
        if upper not in allowed:
            raise ValueError(
                f"Invalid log level: {value!r}. Must be one of: {sorted(allowed)}"
            )
        return upper
