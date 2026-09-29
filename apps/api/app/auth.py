"""Authenticated-identity boundary for the FastAPI backend (Task 3.2).

A single place turns a request's Supabase access token into an identity that
future protected endpoints can depend on::

    @app.get("/example")
    def example(user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)]):
        ...

No endpoint uses it yet. Identity is derived **only** from a token verified
with Supabase Auth — never from a body, query, or header value the client
chose, so a caller cannot claim to be someone else.

Failures are explicit and safe: 401 for a missing, malformed, or rejected
token, and 503 when Supabase is unconfigured or unreachable. Provider error
text is never returned and never logged; logs record the exception type only.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel
from supabase import AuthError, AuthRetryableError

from app.config import Settings, get_settings
from app.logging_config import logger
from app.supabase_client import SupabaseNotConfiguredError, get_supabase_client

BEARER_SCHEME = "Bearer"
BEARER_CHALLENGE = {"WWW-Authenticate": "Bearer"}


class AuthUserLike(Protocol):
    """The parts of a Supabase user this module reads."""

    id: str
    email: str | None


class UserResponseLike(Protocol):
    """The parts of a Supabase `get_user` response this module reads."""

    user: AuthUserLike | None


class SupabaseAuthLike(Protocol):
    """The Supabase Auth surface this module uses."""

    def get_user(self, jwt: str | None = None) -> UserResponseLike | None:
        """Return the user a token belongs to, or `None` when there is none."""


class SupabaseClientLike(Protocol):
    """The Supabase client surface this module uses."""

    auth: SupabaseAuthLike


class InvalidAccessTokenError(Exception):
    """A token that cannot be accepted: absent, malformed, expired, or unknown.

    ``detail`` is a fixed, safe message chosen by this module — never provider
    text — so it can be returned to the caller as-is.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class AuthenticationUnavailableError(Exception):
    """The token could not be verified at all (Supabase unreachable or unusable)."""


class AuthenticatedUser(BaseModel):
    """The signed-in identity a request acts as, derived from a verified token."""

    user_id: str
    email: str | None = None


class AccessTokenVerifier(Protocol):
    """How the authentication dependency obtains an identity from a token."""

    def verify(self, access_token: str) -> AuthenticatedUser:
        """Return the identity for ``access_token`` or raise on rejection."""


class SupabaseAccessTokenVerifier:
    """Verify access tokens with Supabase Auth using the server-side client.

    ``client_factory`` is the seam tests replace with a fake; production uses
    the shared backend client from :mod:`app.supabase_client`, which is built
    from the service-role key and never from a browser credential.
    """

    def __init__(
        self,
        settings: Settings,
        client_factory: Callable[[Settings], SupabaseClientLike] = get_supabase_client,
    ) -> None:
        self._settings = settings
        self._client_factory = client_factory

    def verify(self, access_token: str) -> AuthenticatedUser:
        """Ask Supabase which user this token belongs to.

        Raises :class:`InvalidAccessTokenError` when Supabase rejects the
        token, :class:`AuthenticationUnavailableError` when verification could
        not be carried out, and lets :class:`SupabaseNotConfiguredError`
        propagate so the caller can answer "not configured".
        """
        try:
            client = self._client_factory(self._settings)
            response = client.auth.get_user(access_token)
        except SupabaseNotConfiguredError:
            raise
        except AuthRetryableError as exc:
            logger.warning(
                "Access token verification unavailable (type=%s).", type(exc).__name__
            )
            raise AuthenticationUnavailableError("Supabase Auth is unreachable.") from exc
        except AuthError as exc:
            logger.warning("Access token rejected (type=%s).", type(exc).__name__)
            raise InvalidAccessTokenError(
                "Authentication credentials are invalid or expired."
            ) from exc
        except Exception as exc:
            # Anything else (transport failure, unexpected SDK shape) is not a
            # rejection — we could not verify, so the caller must not be granted
            # access. Only the type is logged; the token never is.
            logger.warning(
                "Access token verification failed (type=%s).", type(exc).__name__
            )
            raise AuthenticationUnavailableError("Supabase Auth could not be used.") from exc

        user = None if response is None else response.user
        if user is None or not isinstance(user.id, str) or user.id == "":
            raise InvalidAccessTokenError(
                "Authentication credentials are invalid or expired."
            )
        return AuthenticatedUser(user_id=user.id, email=user.email)


def extract_access_token(authorization: str | None) -> str:
    """Return the bearer token from an ``Authorization`` header value.

    A missing or malformed header is rejected rather than guessed at. The
    returned token is passed straight to Supabase and is never logged.
    """
    if authorization is None or authorization.strip() == "":
        raise InvalidAccessTokenError("Authentication required.")

    # Trim the header as a whole first: proxies and clients may pad it, and the
    # leading whitespace must not become part of the scheme.
    scheme, separator, credentials = authorization.strip().partition(" ")
    if (
        separator == ""
        or scheme.lower() != BEARER_SCHEME.lower()
        or credentials.strip() == ""
    ):
        raise InvalidAccessTokenError(
            "The Authorization header must be a Bearer token."
        )
    return credentials.strip()


def _unauthorized(detail: str) -> HTTPException:
    """Build the 401 response shape, challenging the client for a bearer token."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers=dict(BEARER_CHALLENGE),
    )


def _authentication_unavailable() -> HTTPException:
    """Build the 503 used when Supabase cannot answer (unconfigured or down)."""
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Authentication is temporarily unavailable.",
    )


def get_access_token_verifier(
    settings: Settings = Depends(get_settings),
) -> AccessTokenVerifier:
    """Provide the token verifier the authentication dependency uses."""
    return SupabaseAccessTokenVerifier(settings)


async def require_authenticated_user(
    authorization: str | None = Header(default=None),
    verifier: AccessTokenVerifier = Depends(get_access_token_verifier),
) -> AuthenticatedUser:
    """Resolve the request's authenticated identity, or fail closed.

    Not applied to any endpoint yet — this is the reusable boundary future
    protected endpoints depend on. The identity comes from the verified token
    only; no client-supplied identifier is ever treated as proof of identity.
    """
    try:
        access_token = extract_access_token(authorization)
        return verifier.verify(access_token)
    except InvalidAccessTokenError as exc:
        raise _unauthorized(exc.detail) from exc
    except SupabaseNotConfiguredError as exc:
        logger.warning("Authentication was requested while Supabase is not configured.")
        raise _authentication_unavailable() from exc
    except AuthenticationUnavailableError as exc:
        raise _authentication_unavailable() from exc

