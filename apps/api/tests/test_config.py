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
    monkeypatch.delenv("AGENTSCHAT_API_LOG_LEVEL", raising=False)

    settings = Settings()

    assert settings.app_name == "AgentsChat API"
    assert settings.environment == "local"
    assert settings.log_level == "INFO"


def test_environment_variables_override_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AGENTSCHAT_API_* variables are applied when present."""
    monkeypatch.setenv("AGENTSCHAT_API_APP_NAME", "AgentsChat Test API")
    monkeypatch.setenv("AGENTSCHAT_API_ENVIRONMENT", "test")
    monkeypatch.setenv("AGENTSCHAT_API_LOG_LEVEL", "DEBUG")

    settings = Settings()

    assert settings.app_name == "AgentsChat Test API"
    assert settings.environment == "test"
    assert settings.log_level == "DEBUG"


def test_unprefixed_variables_are_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Variables without the AGENTSCHAT_API_ prefix cannot leak in from a shared process env."""
    monkeypatch.delenv("AGENTSCHAT_API_APP_NAME", raising=False)
    monkeypatch.delenv("AGENTSCHAT_API_ENVIRONMENT", raising=False)
    monkeypatch.delenv("AGENTSCHAT_API_LOG_LEVEL", raising=False)
    monkeypatch.setenv("APP_NAME", "Not the API's setting")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    settings = Settings()

    assert settings.app_name == "AgentsChat API"
    assert settings.environment == "local"
    assert settings.log_level == "INFO"


def test_empty_environment_name_is_rejected() -> None:
    """An empty environment name fails validation with the offending field named."""
    with pytest.raises(ValidationError, match="environment"):
        Settings(environment="")


def test_empty_app_name_is_rejected() -> None:
    """An empty application name fails validation with the offending field named."""
    with pytest.raises(ValidationError, match="app_name"):
        Settings(app_name="")


def test_invalid_log_level_is_rejected() -> None:
    """An unknown log level fails validation with the offending field named."""
    with pytest.raises(ValidationError, match="log_level"):
        Settings(log_level="VERBOSE")  # type: ignore[arg-type]


def test_half_pair_error_does_not_print_service_role_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("AGENTSCHAT_API_SUPABASE_URL", raising=False)
    key = "test-sensitive-service-role-key"
    monkeypatch.setenv("AGENTSCHAT_API_SUPABASE_SERVICE_ROLE_KEY", key)

    with pytest.raises(ValidationError) as caught:
        Settings()

    print(caught.value)
    output = capsys.readouterr().out
    assert "must be set together" in output
    assert key not in output


def test_settings_representation_omits_service_role_key() -> None:
    key = "test-sensitive-service-role-key"
    settings = Settings(
        supabase_url="https://example.supabase.co", supabase_service_role_key=key
    )

    assert key not in repr(settings)
    assert key not in str(settings)


@pytest.mark.parametrize("blank", ["", " ", "\t\n"])
@pytest.mark.parametrize("pair", ["url", "key", "both", "url_only", "key_only"])
def test_blank_supabase_credentials_are_rejected(blank: str, pair: str) -> None:
    url = blank if pair in ("url", "both", "url_only") else "https://example.supabase.co"
    key = blank if pair in ("key", "both", "key_only") else "test-service-role-key"
    if pair == "url_only":
        key = None
    elif pair == "key_only":
        url = None

    with pytest.raises(ValidationError, match="supabase"):
        Settings(supabase_url=url, supabase_service_role_key=key)
