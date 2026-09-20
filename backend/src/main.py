"""FastAPI application entrypoint."""

from fastapi import FastAPI

app = FastAPI(title="AgentsChat API")


@app.get("/health")
async def health() -> dict[str, str]:
    """Report that the API process is up."""
    return {"status": "ok", "service": "agentschat-api"}
