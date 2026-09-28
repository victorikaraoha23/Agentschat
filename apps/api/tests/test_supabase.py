"""Supabase integration boundary: configuration, initialization, missing-config handling (Task 3.1)."""

import logging

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.supabase_client import (
    SupabaseNotConfiguredError,
    get_supabase_client,
    is_supabase_configured,
)


def test_supabase_defaults_to_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no Supabase variables, settings report unconfigured — local dev must not break."""
    monkeypatch.delenv("AGENTSCHAT_API_SUPABASE_URL", raising=False)
    monkeypatch.delenv("AGENTSCHAT_API_SUPABASE_SERVICE_ROLE_KEY", raising=False)

    settings = Settings()

    assert settings.supabase_url is None
    assert settings.supabase_service_role_key is None
    assert settings.supabase_configured is False
    assert is_supabase_configured(settings) is False


def test_supabase_pair_loads_together(monkeypatch: pytest.MonkeyPatch) -> None:
    """URL and service-role key are read from the AGENTSCHAT_API_* namespace."""
    monkeypatch.setenv("AGENTSCHAT_API_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("AGENTSCHAT_API_SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")

    settings = Settings()

    assert settings.supabase_url == "https://example.supabase.co"
    assert settings.supabase_service_role_key == "test-service-role-key"
    assert settings.supabase_configured is True
    assert is_supabase_configured(settings) is True


@pytest.mark.parametrize(
    "url,key",
    [
        ("https://example.supabase.co", None),
        (None, "test-service-role-key"),
    ],
)
def test_half_configured_supabase_pair_is_rejected(url: str | None, key: str | None) -> None:
    """A URL without a key (or key without URL) fails validation naming the pair."""
    with pytest.raises(ValueError, match="supabase_url and supabase_service_role_key"):
        Settings(supabase_url=url, supabase_service_role_key=key)  # type: ignore[arg-type]


def test_client_creation_fails_clearly_when_unconfigured() -> None:
    """Missing configuration raises a clear error — never a client with placeholders."""
    settings = Settings(supabase_url=None, supabase_service_role_key=None)

    with pytest.raises(SupabaseNotConfiguredError, match="Supabase is not configured"):
        get_supabase_client(settings)


def test_client_initializes_from_valid_configuration() -> None:
    """A complete pair builds an SDK client — construction only, no network call."""
    settings = Settings(
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="test-service-role-key",
    )

    client = get_supabase_client(settings)

    assert client is not None


def test_lifespan_runs_unconfigured_without_crashing(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Startup with no Supabase variables logs the state and still serves /health."""
    caplog.set_level(logging.INFO, logger="agentschat")
    settings = Settings(supabase_url=None, supabase_service_role_key=None)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
    assert any(
        "Supabase is not configured" in record.message for record in caplog.records
    )
