"""Centralized, validated settings for the FastAPI application.

Every value comes from an ``AGENTSCHAT_API_*`` environment variable and carries a safe
local-development default, so the API starts with no ``.env`` file and no secrets
(root ``AGENTS.md`` §16). Only settings with a concrete current use live here (§5, §21).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevelName = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Application settings read from the process environment."""

    # The prefix keeps this app's variables from colliding with the Hermes runtime's,
    # which can share the process environment, and makes them greppable as one family.
    model_config = SettingsConfigDict(env_prefix="AGENTSCHAT_API_")

    app_name: str = Field(
        default="AgentsChat API",
        min_length=1,
        description="Application name; also the OpenAPI document title.",
    )
    environment: str = Field(
        default="local",
        min_length=1,
        description="Environment label for local development.",
    )
    log_level: LogLevelName = Field(
        default="INFO",
        description="Root log level for local-development output (e.g. INFO, DEBUG).",
    )
    supabase_url: str | None = Field(
        default=None,
        description=(
            "Supabase project URL (backend uses the service-role key, never the "
            "browser anon key). None means Supabase is unconfigured; local "
            "development runs without it."
        ),
    )
    supabase_service_role_key: str | None = Field(
        default=None,
        description=(
            "Privileged Supabase service-role key — server-only, never exposed "
            "to the browser. None means Supabase is unconfigured."
        ),
    )

    @model_validator(mode="after")
    def _require_both_supabase_values(self) -> Settings:
        """Reject a half-configured Supabase pair — URL with no key, or key with no URL."""
        if (self.supabase_url is None) != (self.supabase_service_role_key is None):
            raise ValueError("supabase_url and supabase_service_role_key must be set together")
        return self

    @property
    def supabase_configured(self) -> bool:
        """Whether backend Supabase credentials are present (both or neither)."""
        return self.supabase_url is not None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance, read once per process."""
    return Settings()
