"""AgentsChat FastAPI application: minimal foundation with a health check."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import get_settings

settings = get_settings()


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
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(DEV_ALLOWED_ORIGINS),
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def read_health() -> HealthResponse:
    """Report that the API process is up and serving requests."""
    return HealthResponse(status="healthy")
