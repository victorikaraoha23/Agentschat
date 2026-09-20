"""Typed application settings.

This module is the **single source of environment variables**.

**Never log this object or any of its fields.** It holds API keys, a Supabase service-role key, a
webhook signing secret, and connection strings. Log ids, event types, durations, and outcomes —
never configuration values.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from the environment and an optional `.env` file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Runtime
    environment: str = "development"
    log_level: str = "info"
    frontend_url: str = "http://localhost:3000"
    worker_concurrency: int = 4

    # Infrastructure
    database_url: str = ""
    redis_url: str = ""
    supabase_url: str = ""
    supabase_jwks_url: str = ""
    supabase_service_role_key: str = ""

    # Billing (Lemon Squeezy)
    lemonsqueezy_api_key: str = ""
    lemonsqueezy_webhook_secret: str = ""
    lemonsqueezy_store_id: str = ""

    # Integrations
    resend_api_key: str = ""
    sentry_dsn: str = ""
    axiom_token: str = ""
    search_api_key: str = ""
    search_provider: str = "brave"

    # Models — never hard-code a model ID in a code path; resolve it from here.
    model_cheap: str = "claude-haiku-4-5-20251001"
    model_mid: str = "claude-sonnet-5"
    model_premium: str = "claude-sonnet-5"
    model_cheap_fallback: str = ""
    model_mid_fallback: str = ""
    model_premium_fallback: str = ""
    allowed_models: str = ""

    @property
    def allowed_models_set(self) -> set[str]:
        """`allowed_models` as a set, split on commas with blank entries dropped."""
        return {model.strip() for model in self.allowed_models.split(",") if model.strip()}

    @property
    def is_production(self) -> bool:
        """True when `environment` is `production`."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """True when `environment` is `development`."""
        return self.environment == "development"


settings = Settings()

