"""Tests for `src.config.Settings`."""

import pytest

from src.config import Settings

# Variables a developer's shell could set, which would otherwise leak into these tests.
OVERRIDABLE = (
    "ENVIRONMENT",
    "LOG_LEVEL",
    "FRONTEND_URL",
    "WORKER_CONCURRENCY",
    "DATABASE_URL",
    "REDIS_URL",
    "SUPABASE_URL",
    "SUPABASE_JWKS_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "LEMONSQUEEZY_API_KEY",
    "LEMONSQUEEZY_WEBHOOK_SECRET",
    "LEMONSQUEEZY_STORE_ID",
    "RESEND_API_KEY",
    "SENTRY_DSN",
    "AXIOM_TOKEN",
    "SEARCH_API_KEY",
    "SEARCH_PROVIDER",
    "MODEL_CHEAP",
    "MODEL_MID",
    "MODEL_PREMIUM",
    "MODEL_CHEAP_FALLBACK",
    "MODEL_MID_FALLBACK",
    "MODEL_PREMIUM_FALLBACK",
    "ALLOWED_MODELS",
)


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear our variables so a test sees only the declared defaults."""
    for name in OVERRIDABLE:
        monkeypatch.delenv(name, raising=False)


def test_defaults(clean_env: None) -> None:
    """Every field falls back to its documented default."""
    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.log_level == "info"
    assert settings.frontend_url == "http://localhost:3000"
    assert settings.worker_concurrency == 4

    assert settings.database_url == ""
    assert settings.redis_url == ""
    assert settings.supabase_url == ""
    assert settings.supabase_jwks_url == ""
    assert settings.supabase_service_role_key == ""

    assert settings.lemonsqueezy_api_key == ""
    assert settings.lemonsqueezy_webhook_secret == ""
    assert settings.lemonsqueezy_store_id == ""

    assert settings.resend_api_key == ""
    assert settings.sentry_dsn == ""
    assert settings.axiom_token == ""
    assert settings.search_api_key == ""
    assert settings.search_provider == "brave"

    assert settings.model_cheap == "claude-haiku-4-5-20251001"
    assert settings.model_mid == "claude-sonnet-5"
    assert settings.model_premium == "claude-sonnet-5"
    assert settings.model_cheap_fallback == ""
    assert settings.model_mid_fallback == ""
    assert settings.model_premium_fallback == ""
    assert settings.allowed_models == ""

    assert settings.allowed_models_set == set()


def test_is_production(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """`is_production` is true only for `production`."""
    assert Settings(_env_file=None).is_production is False

    monkeypatch.setenv("ENVIRONMENT", "production")

    assert Settings(_env_file=None).is_production is True


def test_is_development(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """`is_development` is true only for `development`."""
    assert Settings(_env_file=None).is_development is True

    monkeypatch.setenv("ENVIRONMENT", "staging")

    assert Settings(_env_file=None).is_development is False


def test_env_override(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables override the defaults."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pw@db:5432/agentschat")
    monkeypatch.setenv("WORKER_CONCURRENCY", "8")
    monkeypatch.setenv("SEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("MODEL_CHEAP_FALLBACK", "gpt-5.6-luna")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+asyncpg://user:pw@db:5432/agentschat"
    assert settings.worker_concurrency == 8
    assert settings.search_provider == "tavily"
    assert settings.model_cheap_fallback == "gpt-5.6-luna"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", set()),
        ("   ", set()),
        (",", set()),
        ("a", {"a"}),
        ("a,b", {"a", "b"}),
        (" a , b ", {"a", "b"}),
        ("a,,b", {"a", "b"}),
        ("a,a", {"a"}),
        ("m1, m2,m3", {"m1", "m2", "m3"}),
    ],
)
def test_allowed_models_set_parsing(
    clean_env: None, monkeypatch: pytest.MonkeyPatch, raw: str, expected: set[str]
) -> None:
    """`allowed_models` is split on commas, trimmed, and de-duplicated."""
    monkeypatch.setenv("ALLOWED_MODELS", raw)

    assert Settings(_env_file=None).allowed_models_set == expected
