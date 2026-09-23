# AgentsChat API

The FastAPI backend/API for AgentsChat. **Foundation stage:** it starts locally and exposes a health
check. It has no product functionality yet — no authentication, database, Supabase, Hermes
integration, or business endpoints.

## Requirements

- Python `>=3.11,<3.14` (the range available in this repository's environment)
- [uv](https://docs.astral.sh/uv/) — the dependency manager already used at the repository root

## Commands

Run from this directory (`apps/api/`):

```powershell
uv sync           # create .venv and install dependencies (writes uv.lock on first run)
uv run pytest     # run the test suite
uv run uvicorn app.main:app --port 8000   # start the API locally
```

`GET http://127.0.0.1:8000/health` then returns `200` with `{"status": "healthy"}`.

## Configuration

Settings are centralized in `app/config.py` (Pydantic Settings) and read from `AGENTSCHAT_API_*`
environment variables. Every setting has a safe default, so no `.env` file is required to start:

| Variable | Default | Purpose |
| --- | --- | --- |
| `AGENTSCHAT_API_APP_NAME` | `AgentsChat API` | Application name; also the OpenAPI document title |
| `AGENTSCHAT_API_ENVIRONMENT` | `local` | Environment label for local development |

Invalid values (for example an empty string) fail validation when settings load, naming the offending
field. This application has no secrets yet, so no `.env.example` exists; the first task that introduces
a value which must be set per environment adds it (root `AGENTS.md` §16).

## Structure

```text
apps/api/
├── app/
│   ├── __init__.py
│   ├── config.py         # centralized settings (AGENTSCHAT_API_*)
│   └── main.py           # FastAPI application + GET /health
├── tests/
│   ├── test_config.py
│   └── test_health.py
├── pyproject.toml       # dependencies + pytest configuration
└── uv.lock              # locked dependency versions
```

## Notes

- This is an **independent project** with its own `pyproject.toml`, `.venv`, and `uv.lock`. It is not part
  of the Hermes root Python package or the Hermes virtualenv — install and run it from inside `apps/api/`.
- The Hermes root `[tool.setuptools.packages.find]` include list does not cover `apps/`, so these files
  are never swept into the Hermes wheel, and the Hermes root pytest `testpaths = ["tests"]` does not
  collect `apps/api/tests`.
