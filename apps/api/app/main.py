"""AgentsChat FastAPI application: health check, identity, and conversations."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from httpx import HTTPError
from pydantic import BaseModel, Field
from supabase import PostgrestAPIError, SupabaseException

from app.auth import AuthenticatedUser, require_authenticated_user
from app.config import Settings, get_settings
from app.conversations import (
    Conversation,
    ConversationCreateError,
    SupabaseConversationStore,
)
from app.logging_config import configure_logging, logger
from app.profiles import (
    ProfileRowNotFoundError,
    SupabaseProfileStore,
    UserProfile,
    load_user_profile,
)
from app.supabase_client import (
    SupabaseNotConfiguredError,
    get_supabase_client,
    is_supabase_configured,
)

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
    allow_methods=["GET", "POST"],
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


#: Longest conversation title the API stores. Long enough for a human-written
#: label, short enough to keep rows and future list views predictable.
MAX_CONVERSATION_TITLE_LENGTH = 200


class CreateConversationRequest(BaseModel):
    """Body of POST /conversations: an optional title, nothing else.

    `user_id` is deliberately absent: ownership always comes from the
    authenticated identity, so a client field by that name must never control
    it. Pydantic ignores unknown fields by default, which means a forged
    `user_id` in the body is dropped before the handler ever sees it.
    """

    title: str | None = Field(default=None, max_length=MAX_CONVERSATION_TITLE_LENGTH)


class ConversationListResponse(BaseModel):
    """Body of GET /conversations: the caller's own conversations, named.

    A wrapped collection rather than a bare array, so the response says what it
    contains and can gain fields without becoming a differently shaped payload.
    """

    items: list[Conversation]


#: Answer for an id that does not exist *or* is not the caller's — deliberately
#: the same message, so a response can never confirm that someone else's
#: conversation exists (root AGENTS.md §10).
CONVERSATION_NOT_FOUND_DETAIL = "Conversation not found."

#: Answer when the read itself failed (Supabase unconfigured, unreachable, or
#: erroring). Fixed text: no SQL, provider payload, or internal detail.
CONVERSATION_LIST_UNAVAILABLE_DETAIL = "The conversations could not be read."
CONVERSATION_UNAVAILABLE_DETAIL = "The conversation could not be read."


def normalize_conversation_title(title: str | None) -> str | None:
    """Trim a title; blank or missing becomes `None` (the schema default)."""
    if title is None:
        return None
    stripped = title.strip()
    return stripped if stripped != "" else None


def get_conversation_store(
    settings: Annotated[Settings, Depends(get_settings)],
) -> SupabaseConversationStore:
    """Provide the conversation store the creation endpoint writes through."""
    return SupabaseConversationStore(settings)


@app.post("/conversations", response_model=Conversation, status_code=status.HTTP_201_CREATED)
def create_conversation(
    body: CreateConversationRequest,
    user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    store: Annotated[SupabaseConversationStore, Depends(get_conversation_store)],
) -> Conversation:
    """Create one conversation owned by the verified caller and return it.

    Ownership is the caller's verified `user_id` — never a client-supplied
    value. The database RLS `insert` policy remains the final boundary.
    """
    try:
        return store.create(user.user_id, normalize_conversation_title(body.title))
    except ConversationCreateError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The conversation could not be created.",
        ) from exc
    except (PostgrestAPIError, SupabaseException, SupabaseNotConfiguredError, HTTPError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The conversation could not be created.",
        ) from exc


@app.get("/conversations", response_model=ConversationListResponse)
def list_conversations(
    user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    store: Annotated[SupabaseConversationStore, Depends(get_conversation_store)],
) -> ConversationListResponse:
    """Return the verified caller's conversations, most recently updated first.

    Identity comes from the Task 3.2 dependency and there is no `user_id`
    parameter to pass: the store scopes the query to that identity in the
    database, so another user's rows are never read, let alone returned. An
    account with no conversations is an empty collection, not an error.
    """
    try:
        return ConversationListResponse(items=store.list_for_user(user.user_id))
    except (PostgrestAPIError, SupabaseException, SupabaseNotConfiguredError, HTTPError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=CONVERSATION_LIST_UNAVAILABLE_DETAIL,
        ) from exc


@app.get("/conversations/{conversation_id}", response_model=Conversation)
def read_conversation(
    conversation_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    store: Annotated[SupabaseConversationStore, Depends(get_conversation_store)],
) -> Conversation:
    """Return one conversation the caller owns, or a 404 it cannot read.

    The path parameter is validated as a UUID before any query runs. Ownership
    is the caller's verified identity — never a body, query, or path value — and
    the store filters on it together with the id, so a conversation belonging to
    someone else produces exactly the same response as one that does not exist.
    """
    try:
        conversation = store.get_for_user(user.user_id, str(conversation_id))
    except (PostgrestAPIError, SupabaseException, SupabaseNotConfiguredError, HTTPError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=CONVERSATION_UNAVAILABLE_DETAIL,
        ) from exc

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=CONVERSATION_NOT_FOUND_DETAIL,
        )
    return conversation


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
    except (PostgrestAPIError, SupabaseException, SupabaseNotConfiguredError, HTTPError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is temporarily unavailable.",
        ) from exc
