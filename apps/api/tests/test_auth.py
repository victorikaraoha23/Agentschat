"""Authenticated-identity boundary: missing, malformed, invalid, and verified tokens (Task 3.2).

Supabase Auth is faked through the module's seams, so no test needs the live
service or credentials.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Annotated

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import BaseModel
from supabase import AuthApiError, AuthRetryableError

from app.auth import (
    AuthenticationUnavailableError,
    AuthenticatedUser,
    InvalidAccessTokenError,
    SupabaseAccessTokenVerifier,
    extract_access_token,
    get_access_token_verifier,
    require_authenticated_user,
)
from app.config import Settings
from app.main import app
from app.supabase_client import SupabaseNotConfiguredError

VALID_TOKEN = "header.payload.signature"

UNCONFIGURED = Settings(supabase_url=None, supabase_service_role_key=None)
CONFIGURED = Settings(
    supabase_url="https://example.supabase.co",
    supabase_service_role_key="test-service-role-key",
)


@dataclass
class FakeUser:
    """The user fields the boundary reads."""

    id: str
    email: str | None


@dataclass
class FakeUserResponse:
    """The `get_user` response shape the boundary reads."""

    user: FakeUser | None


class FakeAuth:
    """Stand-in for `client.auth`."""

    def __init__(self, outcome: FakeUserResponse | None | Exception) -> None:
        self._outcome = outcome
        self.requested_tokens: list[str | None] = []

    def get_user(self, jwt: str | None = None) -> FakeUserResponse | None:
        self.requested_tokens.append(jwt)
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


class FakeClient:
    """Stand-in for the Supabase client."""

    def __init__(self, outcome: FakeUserResponse | None | Exception) -> None:
        self.auth = FakeAuth(outcome)


class FakeVerifier:
    """Stand-in for the token verifier the dependency depends on."""

    def __init__(self, outcome: AuthenticatedUser | Exception) -> None:
        self._outcome = outcome
        self.requested_tokens: list[str] = []

    def verify(self, access_token: str) -> AuthenticatedUser:
        self.requested_tokens.append(access_token)
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


class ClaimedIdentity(BaseModel):
    """A request body that claims an identity, which must never be trusted."""

    user_id: str


@contextmanager
def protected_route(
    verifier: FakeVerifier, path: str = "/_test/whoami"
) -> Iterator[None]:
    """Serve `path` behind the authentication dependency, then restore state.

    The route and the dependency override exist only inside the test: the
    application must not gain an endpoint (or a swapped verifier) merely to be
    testable, because protected endpoints belong to a later task.
    """
    previous_routes = list(app.router.routes)
    previous_overrides = dict(app.dependency_overrides)

    async def endpoint(
        user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    ) -> AuthenticatedUser:
        return user

    async def claimed_identity_endpoint(
        user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
        claim: ClaimedIdentity,
    ) -> AuthenticatedUser:
        # `claim` is accepted and ignored on purpose: body-supplied identity is
        # not, and must never become, proof of identity.
        return user

    app.dependency_overrides[get_access_token_verifier] = lambda: verifier
    app.get(path)(endpoint)
    app.post(f"{path}/claim")(claimed_identity_endpoint)
    try:
        yield
    finally:
        app.router.routes = previous_routes
        app.dependency_overrides = previous_overrides


def test_missing_authorization_header_is_rejected() -> None:
    """No Authorization header means 401 with a bearer challenge."""
    with protected_route(FakeVerifier(AuthenticatedUser(user_id="user-1"))):
        response = TestClient(app).get("/_test/whoami")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "header",
    [
        "Basic dXNlcjpwYXNzd29yZA==",
        "Bearer",
        "Bearer ",
        f"Token {VALID_TOKEN}",
    ],
)
def test_malformed_authorization_header_is_rejected(header: str) -> None:
    """A non-bearer or incomplete Authorization header is rejected, not guessed at."""
    verifier = FakeVerifier(AuthenticatedUser(user_id="user-1"))

    with protected_route(verifier):
        response = TestClient(app).get("/_test/whoami", headers={"Authorization": header})

    assert response.status_code == 401
    assert response.json() == {"detail": "The Authorization header must be a Bearer token."}
    assert verifier.requested_tokens == []


def test_rejected_token_returns_401_without_provider_detail() -> None:
    """A token Supabase rejects is a 401 with our own fixed message."""
    verifier = FakeVerifier(
        InvalidAccessTokenError("Authentication credentials are invalid or expired.")
    )

    with protected_route(verifier):
        response = TestClient(app).get(
            "/_test/whoami", headers={"Authorization": f"Bearer {VALID_TOKEN}"}
        )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Authentication credentials are invalid or expired."
    }
    assert VALID_TOKEN not in response.text
    assert verifier.requested_tokens == [VALID_TOKEN]


def test_verified_token_yields_the_authenticated_identity() -> None:
    """A valid token resolves to the identity Supabase reported for it."""
    verifier = FakeVerifier(
        AuthenticatedUser(user_id="user-1", email="person@example.com")
    )

    with protected_route(verifier):
        response = TestClient(app).get(
            "/_test/whoami", headers={"Authorization": f"bearer  {VALID_TOKEN} "}
        )

    assert response.status_code == 200
    assert response.json() == {"user_id": "user-1", "email": "person@example.com"}
    # The scheme is matched case-insensitively and the token is passed through
    # exactly, without surrounding whitespace.
    assert verifier.requested_tokens == [VALID_TOKEN]


def test_a_claimed_identity_in_the_body_is_ignored() -> None:
    """A body-supplied user id can never become the authenticated identity."""
    verifier = FakeVerifier(AuthenticatedUser(user_id="real-user"))

    with protected_route(verifier):
        response = TestClient(app).post(
            "/_test/whoami/claim",
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
            json={"user_id": "someone-else"},
        )

    assert response.status_code == 200
    assert response.json() == {"user_id": "real-user", "email": None}


def test_unauthenticated_requests_are_distinguishable_from_authenticated_ones() -> None:
    """The same endpoint answers 401 without a token and 200 with one."""
    verifier = FakeVerifier(AuthenticatedUser(user_id="user-1"))

    with protected_route(verifier):
        anonymous = TestClient(app).get("/_test/whoami")
        authenticated = TestClient(app).get(
            "/_test/whoami", headers={"Authorization": f"Bearer {VALID_TOKEN}"}
        )

    assert anonymous.status_code == 401
    assert authenticated.status_code == 200
    assert anonymous.json() != authenticated.json()


def test_health_stays_public() -> None:
    """The health check never requires authentication, with or without Supabase."""
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_unconfigured_supabase_makes_authentication_unavailable(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no credentials the real verifier fails clearly instead of faking a user."""
    monkeypatch.delenv("AGENTSCHAT_API_SUPABASE_URL", raising=False)
    monkeypatch.delenv("AGENTSCHAT_API_SUPABASE_SERVICE_ROLE_KEY", raising=False)
    caplog.set_level(logging.WARNING, logger="agentschat")
    verifier = SupabaseAccessTokenVerifier(UNCONFIGURED)

    with protected_route(verifier):
        response = TestClient(app).get(
            "/_test/whoami", headers={"Authorization": f"Bearer {VALID_TOKEN}"}
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication is temporarily unavailable."}
    assert VALID_TOKEN not in response.text
    assert any(
        "Supabase is not configured" in record.getMessage() for record in caplog.records
    )


def test_unreachable_supabase_is_unavailable_not_unauthenticated() -> None:
    """A reachable-but-failing provider answers 503, so it never looks like a bad token."""
    verifier = FakeVerifier(
        AuthenticationUnavailableError("Supabase Auth is unreachable.")
    )

    with protected_route(verifier):
        response = TestClient(app).get(
            "/_test/whoami", headers={"Authorization": f"Bearer {VALID_TOKEN}"}
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication is temporarily unavailable."}


def test_the_verifier_reads_the_identity_from_supabase() -> None:
    """The real verifier turns a Supabase user response into our identity model."""
    client = FakeClient(FakeUserResponse(user=FakeUser(id="user-9", email="a@example.com")))
    verifier = SupabaseAccessTokenVerifier(CONFIGURED, client_factory=lambda _: client)

    identity = verifier.verify(VALID_TOKEN)

    assert identity == AuthenticatedUser(user_id="user-9", email="a@example.com")
    assert client.auth.requested_tokens == [VALID_TOKEN]


@pytest.mark.parametrize("outcome", [None, FakeUserResponse(user=None)])
def test_a_response_without_a_user_is_rejected(
    outcome: FakeUserResponse | None,
) -> None:
    """An empty Supabase answer is a rejection, never an anonymous identity."""
    client = FakeClient(outcome)
    verifier = SupabaseAccessTokenVerifier(CONFIGURED, client_factory=lambda _: client)

    with pytest.raises(InvalidAccessTokenError, match="invalid or expired"):
        verifier.verify(VALID_TOKEN)


def test_an_sdk_rejection_becomes_an_invalid_token() -> None:
    """Supabase's own auth error is translated to our rejection type."""
    client = FakeClient(
        AuthApiError("invalid JWT: signature verification failed", 401, "bad_jwt")
    )
    verifier = SupabaseAccessTokenVerifier(CONFIGURED, client_factory=lambda _: client)

    with pytest.raises(InvalidAccessTokenError) as rejection:
        verifier.verify(VALID_TOKEN)

    # The provider's message is not carried over into ours.
    assert "signature verification failed" not in str(rejection.value)


def test_a_retryable_sdk_failure_is_unavailable_not_invalid() -> None:
    """A transient provider failure must not be reported as a bad credential."""
    client = FakeClient(AuthRetryableError("project is paused", 503))
    verifier = SupabaseAccessTokenVerifier(CONFIGURED, client_factory=lambda _: client)

    with pytest.raises(AuthenticationUnavailableError):
        verifier.verify(VALID_TOKEN)


def test_an_unconfigured_factory_propagates_not_configured() -> None:
    """Client construction without credentials raises, and the token is not used."""

    def factory(_: Settings) -> FakeClient:
        raise SupabaseNotConfiguredError("Supabase is not configured")

    verifier = SupabaseAccessTokenVerifier(UNCONFIGURED, client_factory=factory)

    with pytest.raises(SupabaseNotConfiguredError):
        verifier.verify(VALID_TOKEN)


def test_rejections_never_log_the_token(caplog: pytest.LogCaptureFixture) -> None:
    """Internal logs record the failure category, never the credential itself."""
    caplog.set_level(logging.WARNING, logger="agentschat")
    client = FakeClient(AuthApiError("invalid JWT", 401, "bad_jwt"))
    verifier = SupabaseAccessTokenVerifier(CONFIGURED, client_factory=lambda _: client)

    with pytest.raises(InvalidAccessTokenError):
        verifier.verify(VALID_TOKEN)

    assert VALID_TOKEN not in caplog.text
    assert "signature" not in caplog.text


@pytest.mark.parametrize(
    "header,expected_detail",
    [
        (None, "Authentication required."),
        ("", "Authentication required."),
        ("   ", "Authentication required."),
        ("Bearer", "The Authorization header must be a Bearer token."),
        ("Basic abc", "The Authorization header must be a Bearer token."),
    ],
)
def test_extract_access_token_rejects_unusable_headers(
    header: str | None, expected_detail: str
) -> None:
    """Header parsing is strict, so a malformed header cannot be mistaken for a token."""
    with pytest.raises(InvalidAccessTokenError) as rejection:
        extract_access_token(header)

    assert rejection.value.detail == expected_detail


def test_extract_access_token_accepts_a_bearer_token() -> None:
    """A well-formed bearer header yields exactly the token."""
    assert extract_access_token(f"Bearer {VALID_TOKEN}") == VALID_TOKEN
    assert extract_access_token(f"bearer {VALID_TOKEN}") == VALID_TOKEN
    assert extract_access_token(f"  Bearer   {VALID_TOKEN}  ") == VALID_TOKEN


