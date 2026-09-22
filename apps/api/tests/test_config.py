"""Tests for the centralized application settings."""

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_defaults_serve_local_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every setting falls back to its safe default when no variables are set."""
    monkeypatch.delenv("AGENTSCHAT_API_APP_NAME", raising=False)
    monkeypatch.delenv("AGENTSCHAT_API_ENVIRONMENT", raising=False)

    settings = Settings()

    assert settings.app_name == "AgentsChat API"
    assert settings.environment == "local"


def test_environment_variables_override_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AGENTSCHAT_API_* variables are applied when present."""
    monkeypatch.setenv("AGENTSCHAT_API_APP_NAME", "AgentsChat Test API")
    monkeypatch.setenv("AGENTSCHAT_API_ENVIRONMENT", "test")

    settings = Settings()

    assert settings.app_name == "AgentsChat Test API"
    assert settings.environment == "test"


def test_unprefixed_variables_are_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Variables without the AGENTSCHAT_API_ prefix cannot leak in from a shared process env."""
    monkeypatch.setenv("APP_NAME", "Not the API's setting")

    settings = Settings()

    assert settings.app_name == "AgentsChat API"
    assert settings.environment == "local"


def test_empty_environment_name_is_rejected() -> None:
    """An empty environment name fails validation with the offending field named."""
    with pytest.raises(ValidationError, match="environment"):
        Settings(environment="")


def test_empty_app_name_is_rejected() -> None:
    """An empty application name fails validation with the offending field named."""
    with pytest.raises(ValidationError, match="app_name"):
        Settings(app_name="")
