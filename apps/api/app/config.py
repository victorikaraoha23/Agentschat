"""Centralized, validated settings for the FastAPI application.

Every value comes from an ``AGENTSCHAT_API_*`` environment variable and carries a safe
local-development default, so the API starts with no ``.env`` file and no secrets
(root ``AGENTS.md`` §16). Only settings with a concrete current use live here (§5, §21).
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance, read once per process."""
    return Settings()
