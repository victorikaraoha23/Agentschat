"""AgentsChat FastAPI application: minimal foundation with a health check."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import get_settings
from app.logging_config import configure_logging, logger

settings = get_settings()

configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Log process boundaries once per startup/shutdown — never per request."""
    logger.info("AgentsChat API starting (environment=%s).", settings.environment)
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
    internal exception text must never reach a client. ``logger.exception``
    records the type, message, and traceback server-side only — the request
    itself (path, headers, body) is never logged.
    """
    logger.exception("Unhandled server exception.")

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
