"""AgentsChat FastAPI application: minimal foundation with a health check."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.auth import AuthenticatedUser, require_authenticated_user
from app.config import get_settings
from app.logging_config import configure_logging, logger
from app.profiles import (
    ProfileRowNotFoundError,
    SupabaseProfileStore,
    UserProfile,
    load_user_profile,
)
from app.supabase_client import get_supabase_client, is_supabase_configured

settings = get_settings()

configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Log process boundaries once per startup/shutdown — never per request."""
    current = get_settings()
    logger.info("AgentsChat API starting (environment=%s).", current.environment)
    if is_supabase_configured(current):
        # Verify the SDK can build the client from settings; no network call.
        # Only the configured/unconfigured state is logged — never the URL or key.
        get_supabase_client(current)
        logger.info("Supabase client initialized.")
    else:
        logger.info("Supabase is not configured; running without it.")
    yield
    logger.info("AgentsChat API shutting down.")


class HealthResponse(BaseModel):
    """Response body of GET /health."""

    status: str


# CORS (Task 1.5, Step 6): the browser calls this API cross-origin — the Next.js
# dev server runs on :3000 while this API runs on :8000 — so an explicit
# allowlist of development origins is required. Never use "*"; production origins
# are added deliberately by the task that introduces deployment.
DEV_ALLOWED_ORIGINS: tuple[str, ...] = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)

app = FastAPI(
    title=settings.app_name,
    description="Backend API for AgentsChat.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(DEV_ALLOWED_ORIGINS),
    allow_methods=["GET"],
    allow_headers=["*"],
)


# Error model (Task 2.2): expected errors keep FastAPI's own `{"detail": ...}` shape —
# `HTTPException`, the router's 404/405, and 422 validation errors are already handled
# by FastAPI. Only unexpected exceptions need an explicit handler so they cannot leak
# internals (root AGENTS.md §10, §13).
async def unhandled_exception_handler(request: Request, _exc: Exception) -> JSONResponse:
    """Answer an unexpected server error with a safe, predictable JSON body.

    The message is deliberately generic. Tracebacks, file paths, secrets, and
    internal exception text must never reach a client or log. Only the
    exception type is logged, without its message, traceback, or request data.
    """
    logger.error("Unhandled server exception (type=%s).", type(_exc).__name__)

    origin = request.headers.get("origin")
    headers: dict[str, str] = {}
    if origin is not None and origin in DEV_ALLOWED_ORIGINS:
        headers = {"Access-Control-Allow-Origin": origin, "Vary": "Origin"}
    return JSONResponse(status_code=500, content={"detail": "Internal server error."}, headers=headers)


app.add_exception_handler(Exception, unhandled_exception_handler)


@app.get("/health", response_model=HealthResponse)
def read_health() -> HealthResponse:
    """Report that the API process is up and serving requests."""
    return HealthResponse(status="healthy")


@app.get("/me", response_model=UserProfile)
def read_current_user_profile(
    user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
) -> UserProfile:
    """Return the AgentsChat profile for the verified caller — nothing else.

    Identity comes from the Task 3.2 dependency, never from the request body:
    a caller can only ever resolve their own row. The body carries the profile
    fields only — no tokens, passwords, credentials, or database internals.
    """
    try:
        return load_user_profile(user.user_id, SupabaseProfileStore(get_settings()))
    except ProfileRowNotFoundError as exc:
        # A verified identity with no row is a data-integrity signal (the
        # trigger normally guarantees the row), so it is a 500, not a 404:
        # 404 would let callers probe which identities have profiles.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The authenticated profile is unavailable.",
        ) from exc
