# AgentsChat API

The FastAPI backend/API for AgentsChat. **Foundation stage:** it starts locally and exposes a health
check, plus a Supabase connectivity boundary (client creation only — no auth, no tables, no queries).
It has no product functionality yet — no authentication, database models, Hermes
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
| `AGENTSCHAT_API_SUPABASE_URL` | *(unset)* | Supabase project URL for the backend client; set together with the key below, or neither |
| `AGENTSCHAT_API_SUPABASE_SERVICE_ROLE_KEY` | *(unset)* | Privileged Supabase service-role key — **server-only**, never exposed to the browser; a URL without a key (or key without URL) fails validation |

Invalid values (for example an empty string) fail validation when settings load, naming the offending
field. Copy `.env.example` to `.env` only when real values exist — never commit the copy (`.env*` files
are ignored). Without Supabase variables the backend reports unconfigured and runs without Supabase;
see `## Supabase` below.

When using `.env`, fill in both Supabase values with non-whitespace values and start with:

```powershell
uv run uvicorn app.main:app --port 8000 --env-file .env
```

The `--env-file` option loads `.env` before the API reads its settings. Settings do not load that file
automatically. To run without Supabase, omit both variables; empty or whitespace-only values are invalid.

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

## Supabase

Connectivity boundary only (no auth, no tables, no queries, no repositories). The backend owns one
module, `app/supabase_client.py` (`get_supabase_client` / `is_supabase_configured` /
`SupabaseNotConfiguredError`), built from the `AGENTSCHAT_API_SUPABASE_*` settings with the
**service-role key** — never the browser anon key. On startup the lifespan verifies the SDK can build the
client (construction only, no network call) and logs only `Supabase client initialized.` or
`Supabase is not configured; running without it.` — never the URL or key. Without both variables the API
runs exactly as before; `GET /health` is unaffected. No endpoint returns credentials.

## Authentication

The backend recognizes an authenticated Supabase user, but **no endpoint requires authentication yet** and
no user profile or application data exists. `app/auth.py` owns the boundary:

| Piece | Purpose |
| --- | --- |
| `AuthenticatedUser` | The identity (`user_id`, `email`) a protected request acts as |
| `require_authenticated_user` | FastAPI dependency that resolves it, or fails closed |
| `SupabaseAccessTokenVerifier` | Verifies a token with Supabase Auth via the server-side client |
| `extract_access_token` | Strict `Authorization: Bearer <token>` parsing |

Identity is derived **only** from a token that Supabase Auth has verified — a `user_id` in a request body,
query string, or custom header is never accepted as proof of identity. To protect a future endpoint:

```python
@app.get("/example")
def example(user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)) -> ...:
    ...
```

Failures are explicit and safe (Task 2.2 error shape, no provider text):

| Case | Status | Body |
| --- | --- | --- |
| No `Authorization` header | `401` | `{"detail": "Authentication required."}` + `WWW-Authenticate: Bearer` |
| Header is not a Bearer token | `401` | `{"detail": "The Authorization header must be a Bearer token."}` |
| Token rejected (`invalid`, expired, unknown) | `401` | `{"detail": "Authentication credentials are invalid or expired."}` |
| Supabase unconfigured or unreachable | `503` | `{"detail": "Authentication is temporarily unavailable."}` |

Tokens are never logged, never returned, and never stored by the API. The access token and refresh token
live only in the browser, where Supabase's own session handling keeps them; the API never receives a
refresh token. `GET /health` stays public and Supabase-free.

## User model (profiles)

Supabase Auth remains the source of truth for authentication; `public.profiles` is the **application-level
user record** — one row per Auth user, keyed by `id uuid primary key references auth.users (id)`, so a
profile can never exist for an arbitrary UUID. The schema lives in
[`supabase/migrations/0001_create_profiles.sql`](../../supabase/migrations/0001_create_profiles.sql)
(versioned, safe to apply to a fresh project; see [`supabase/README.md`](../../supabase/README.md)).

- **Creation:** an `after insert on auth.users` trigger creates the row exactly when the Auth identity
  appears (`on conflict do nothing`, so it is idempotent and no duplicate can be created). The frontend
  never creates profiles, and the API never inserts into `profiles`.
- **RLS:** enabled with a single `select` policy scoped to `auth.uid() = id`. No `insert`, `update`, or
  `delete` policy exists — the initial model has no user-editable fields, so no write permission is
  granted at all.
- **Reading:** `app/profiles.py` (`SupabaseProfileStore`, `load_user_profile`,
  `ProfileRowNotFoundError`) resolves one row for the identity the Task 3.2 dependency already verified.

`GET /me` is the single endpoint that proves the bridge: it requires a valid authenticated user
(`require_authenticated_user`), resolves that user's profile, and returns
`{user_id, created_at, updated_at}` — no tokens, passwords, credentials, or database internals. Identity
never comes from the request body or query.

| Case | Status | Body |
| --- | --- | --- |
| No / malformed / rejected token | `401` | (as in `## Authentication` above) |
| Supabase unconfigured or unreachable | `503` | `{"detail": "Authentication is temporarily unavailable."}` |
| Verified identity with no profile row | `500` | `{"detail": "The authenticated profile is unavailable."}` (a data-integrity signal, deliberately not a `404` callers could probe) |

## Structure

```text
apps/api/
├── app/
│   ├── __init__.py
│   ├── auth.py           # authenticated-identity boundary (verified token → user)
│   ├── config.py         # centralized settings (AGENTSCHAT_API_*)
│   ├── logging_config.py # central logging setup (stdlib only, LOG_FORMAT)
│   ├── profiles.py       # profile store + lookup (verified identity → profile row)
│   ├── supabase_client.py # backend Supabase boundary (service-role key, server-only)
│   └── main.py           # FastAPI application + GET /health + GET /me
├── tests/
│   ├── test_auth.py
│   ├── test_config.py
│   ├── test_cors.py
│   ├── test_error_handling.py
│   ├── test_health.py
│   ├── test_logging.py
│   ├── test_profiles.py
│   └── test_supabase.py
├── .env.example         # documents AGENTSCHAT_API_SUPABASE_* (placeholders only, committable)
├── pyproject.toml       # dependencies + pytest configuration
└── uv.lock              # locked dependency versions
```

## Notes

- This is an **independent project** with its own `pyproject.toml`, `.venv`, and `uv.lock`. It is not part
  of the Hermes root Python package or the Hermes virtualenv — install and run it from inside `apps/api/`.
- The Hermes root `[tool.setuptools.packages.find]` include list does not cover `apps/`, so these files
  are never swept into the Hermes wheel, and the Hermes root pytest `testpaths = ["tests"]` does not
  collect `apps/api/tests`.
