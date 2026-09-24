"""CORS policy for the browser-side Next.js -> FastAPI boundary (Task 1.5)."""

from fastapi.testclient import TestClient

from app.main import DEV_ALLOWED_ORIGINS, app

client = TestClient(app)


def test_allowed_dev_origin_receives_cors_header() -> None:
    """The Next.js dev origin may read cross-origin responses."""
    response = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_127_loopback_origin_also_allowed() -> None:
    """Both dev origins from the allowlist are honored."""
    response = client.get("/health", headers={"Origin": "http://127.0.0.1:3000"})
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"


def test_unknown_origin_gets_no_cors_header() -> None:
    """An unlisted origin receives no ACAO header, so the browser blocks it."""
    response = client.get("/health", headers={"Origin": "https://evil.example"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_allowlist_contains_no_wildcard() -> None:
    """The development allowlist must never become a blanket policy."""
    assert "*" not in DEV_ALLOWED_ORIGINS


def test_preflight_allows_get_from_dev_origin() -> None:
    """A preflight for GET succeeds from an allowed development origin."""
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"