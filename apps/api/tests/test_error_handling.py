"""Error-handling behavior: predictable shapes, no leaked internals (Task 2.2)."""

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import DEV_ALLOWED_ORIGINS, app

client = TestClient(app)


@contextmanager
def raising_route(path: str, exc: Exception) -> Iterator[None]:
    """Serve `path` with a route that raises `exc`, then restore the route table.

    The route exists only inside a test — triggering a genuine unexpected exception
    needs something that raises, and the application must not gain a permanent
    endpoint just to be testable.
    """

    def endpoint() -> None:
        raise exc

    previous_routes = list(app.router.routes)
    app.get(path)(endpoint)
    try:
        yield
    finally:
        app.router.routes = previous_routes


def test_unknown_path_keeps_the_detail_shape() -> None:
    """A missing resource returns the predictable error body."""
    response = client.get("/definitely-not-a-route")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_unsupported_method_keeps_the_detail_shape() -> None:
    """An unsupported method on a known path returns the same shape."""
    response = client.post("/health")

    assert response.status_code == 405
    assert response.json() == {"detail": "Method Not Allowed"}


def test_expected_http_error_keeps_its_status_and_detail() -> None:
    """A raised HTTPException passes through unchanged."""
    expected = HTTPException(status_code=409, detail="A run with this id is already running.")

    with raising_route("/_test/expected-error", expected):
        response = client.get("/_test/expected-error")

    assert response.status_code == 409
    assert response.json() == {"detail": "A run with this id is already running."}


def test_unexpected_exception_returns_a_safe_500() -> None:
    """An unhandled exception becomes a generic JSON 500 with nothing internal in it."""
    internal_detail = "RuntimeError in /home/agentschat/app/main.py token=abc123"

    with raising_route("/_test/unexpected-error", RuntimeError(internal_detail)):
        # raise_server_exceptions=False lets the test observe the response a real
        # client would receive instead of the exception being re-raised into the test.
        response = TestClient(app, raise_server_exceptions=False).get("/_test/unexpected-error")

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"detail": "Internal server error."}

    body = response.text
    for leaked in ("RuntimeError", "token=abc123", "/home/agentschat", "main.py", "Traceback", "_test"):
        assert leaked not in body


def test_unexpected_exception_allows_only_dev_origins() -> None:
    """Allowed browser origins can read safe 500s; other origins cannot."""
    with raising_route("/_test/cors-error", RuntimeError("private detail")):
        for origin in (*DEV_ALLOWED_ORIGINS, "https://evil.example", None):
            headers = {"Origin": origin} if origin is not None else {}
            response = TestClient(app, raise_server_exceptions=False).get(
                "/_test/cors-error", headers=headers
            )

            assert response.status_code == 500
            assert response.json() == {"detail": "Internal server error."}
            if origin in DEV_ALLOWED_ORIGINS:
                assert response.headers["access-control-allow-origin"] == origin
                assert response.headers["vary"] == "Origin"
            else:
                assert "access-control-allow-origin" not in response.headers
                assert "vary" not in response.headers


def test_health_response_is_still_unwrapped() -> None:
    """Success responses are not wrapped in an envelope by the error handling."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
