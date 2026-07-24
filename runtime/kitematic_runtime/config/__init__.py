"""Configuration — pydantic-settings based runtime configuration.

Provides RuntimeSettings loaded from environment variables (KITEMATIC_* prefix)
and .env file. All defaults match the existing hardcoded values for
backward compatibility.

Secrets are in a separate SecretsModel to enforce the boundary between
configuration and credentials.

Sources (in priority order):
  1. Explicit constructor args
  2. Environment variables (KITEMATIC_*, KITEMATIC_SECRETS_*)
  3. .env file
  4. Hardcoded defaults
"""

from runtime.kitematic_runtime.config.secrets import SecretsModel, create_secrets_provider
from runtime.kitematic_runtime.config.settings import RuntimeSettings

__all__ = [
    "RuntimeSettings",
    "SecretsModel",
    "create_secrets_provider",
]
