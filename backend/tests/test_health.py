"""Tests for the health endpoint."""

from fastapi.testclient import TestClient

from src.main import app


def test_health_returns_ok() -> None:
    """GET /health returns 200 with the exact service envelope."""
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "agentschat-api"}
