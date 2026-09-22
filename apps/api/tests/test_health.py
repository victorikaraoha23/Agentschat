"""Tests for the health endpoint."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200_with_exact_body() -> None:
    """GET /health answers 200 with exactly {"status": "healthy"} and no extra fields."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
