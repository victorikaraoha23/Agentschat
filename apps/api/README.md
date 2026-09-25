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
| `AGENTSCHAT_API_LOG_LEVEL` | `INFO` | Root log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`); unknown values fail validation |

Invalid values (for example an empty string) fail validation when settings load, naming the offending
field. This application has no secrets yet, so no `.env.example` exists; the first task that introduces
a value which must be set per environment adds it (root `AGENTS.md` §16).

## CORS

The health check is called **from the browser**: the Next.js app runs on `http://localhost:3000` while
this API runs on `http://127.0.0.1:8000`, so the API allows exactly those two development origins
(`DEV_ALLOWED_ORIGINS` in `app/main.py`) for `GET` requests. There is no wildcard origin, and no
production origin is configured yet — that belongs to the task that introduces deployment. An unlisted
origin receives no `access-control-allow-origin` header, so the browser blocks it.

## Errors

Error responses share a JSON `detail` field. Its value depends on the error, including validation errors:

| Case | Status | Body |
| --- | --- | --- |
| Unknown path | `404` | `{"detail": "Not Found"}` |
| Unsupported method on a known path | `405` | `{"detail": "Method Not Allowed"}` |
| Invalid input | `422` | FastAPI's validation detail |
| Raised `HTTPException` | as raised | `{"detail": "<message>"}` |
| **Unexpected exception** | `500` | `{"detail": "Internal server error."}` |

Success responses (including `GET /health`) are returned unwrapped — there is no response envelope.
Unexpected exceptions are answered by `unhandled_exception_handler` in `app/main.py`, which always returns
that fixed message: tracebacks, file paths, secrets, environment values, and internal exception text never
reach a client. The same handler logs only the exception type, without its message, traceback, or request
data.

## Logging

Logging is centralized in `app/logging_config.py` and uses only Python's standard `logging` module — no
external service, no custom framework, no log aggregation. Import-time `configure_logging` applies the
`AGENTSCHAT_API_LOG_LEVEL` setting to the root logger. When no root handler exists, it adds one with a
readable local-development format (`LOG_FORMAT`: timestamp, level, logger name, message). Existing handlers
and their formatters are preserved. `INFO` is the default; `DEBUG` is available for local troubleshooting.

Logged events are deliberately minimal — process boundaries and unexpected failures only:

| Event | Level | Message |
| --- | --- | --- |
| Startup | `INFO` | `AgentsChat API starting (environment=…).` |
| Shutdown | `INFO` | `AgentsChat API shutting down.` |
| Unexpected exception | `ERROR` | `Unhandled server exception (type=…).` |

Request logging is intentionally absent: Uvicorn's own access logs already cover requests, so duplicating
them would only add noise. Nothing logs passwords, tokens, API keys, secrets, cookies, authorization
headers, full request bodies, user private data, environment values, or database credentials.

## Structure

```text
apps/api/
├── app/
│   ├── __init__.py
│   ├── config.py         # centralized settings (AGENTSCHAT_API_*)
│   ├── logging_config.py # central logging setup (stdlib only, LOG_FORMAT)
│   └── main.py           # FastAPI application + GET /health
├── tests/
│   ├── test_config.py
│   ├── test_cors.py
│   ├── test_error_handling.py
│   ├── test_health.py
│   └── test_logging.py
├── pyproject.toml       # dependencies + pytest configuration
└── uv.lock              # locked dependency versions
```

## Notes

- This is an **independent project** with its own `pyproject.toml`, `.venv`, and `uv.lock`. It is not part
  of the Hermes root Python package or the Hermes virtualenv — install and run it from inside `apps/api/`.
- The Hermes root `[tool.setuptools.packages.find]` include list does not cover `apps/`, so these files
  are never swept into the Hermes wheel, and the Hermes root pytest `testpaths = ["tests"]` does not
  collect `apps/api/tests`.
