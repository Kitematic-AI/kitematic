"""Secrets — credential boundary separate from configuration.

RuntimeSettings is for configuration (non-sensitive).
SecretsModel is for credentials (sensitive, short-lived, rotatable).

Sources (priority order):
  1. Direct constructor args
  2. Environment variables
  3. .env file
  4. File-based provider (placeholder for future vault/encrypted file support)

Design principles:
  - SecretsModel is frozen — credentials cannot change during execution.
  - No encryption implementation yet. The file provider is a placeholder
    interface for future vault integration (e.g. HashiCorp Vault, KMS).
  - API keys are stored as SHA-256 fingerprints, never raw.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SecretsModel(BaseModel):
    """Secrets and credentials for the Runtime.

    Separate from RuntimeSettings to enforce the boundary between
    configuration and credentials.

    All fields have safe defaults — empty strings mean "not configured".
    """

    model_config = {"frozen": True}

    admin_api_key: str = Field(default="", description="Admin API key for initial setup")
    api_key_salt: str = Field(default="", description="Salt for API key fingerprinting")


def create_secrets_provider(
    env_prefix: str = "KITEMATIC_SECRETS_",
    secrets_file: str = "",
) -> SecretsModel:
    """Create a SecretsModel from available sources.

    Priority:
      1. env_prefix + field name (e.g. KITEMATIC_SECRETS_ADMIN_API_KEY)
      2. secrets_file (.env-style key=value file)
      3. Defaults (empty strings)

    Args:
        env_prefix: Prefix for environment variable lookup.
        secrets_file: Optional path to a .env-style secrets file.

    Returns:
        A frozen SecretsModel instance.

    File-based secrets provider is a placeholder — no encryption
    is implemented at this stage. In production, use environment
    variables or a vault integration.
    """
    import os

    data: dict[str, str] = {}

    # 1. Environment variables
    for field_name in SecretsModel.model_fields:
        env_var = f"{env_prefix}{field_name.upper()}"
        value = os.environ.get(env_var)
        if value:
            data[field_name] = value

    # 2. File-based provider (placeholder — no encryption)
    if secrets_file:
        try:
            with open(secrets_file) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    field_name = key.strip().lower()
                    if field_name in SecretsModel.model_fields and field_name not in data:
                        data[field_name] = value.strip()
        except FileNotFoundError:
            pass

    return SecretsModel(**data)
