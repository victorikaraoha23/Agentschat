"""AgentsChat FastAPI application: minimal foundation with a health check."""

from fastapi import FastAPI
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response body of GET /health."""

    status: str


app = FastAPI(
    title="AgentsChat API",
    description="Backend API for AgentsChat.",
    version="0.1.0",
)


@app.get("/health", response_model=HealthResponse)
def read_health() -> HealthResponse:
    """Report that the API process is up and serving requests."""
    return HealthResponse(status="healthy")
