# AgentsChat API

The FastAPI backend/API for AgentsChat. **Foundation stage:** it starts locally and exposes a health
check, the authentication boundary, the `GET /me` profile read, and the conversation endpoints —
`POST /conversations`, `GET /conversations`, `GET /conversations/{conversation_id}`,
`PATCH /conversations/{conversation_id}`, and `DELETE /conversations/{conversation_id}` — all backed by
Supabase. It has no chat, agent execution, or Hermes integration yet.

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
(`DEV_ALLOWED_ORIGINS` in `app/main.py`) for `GET`, `POST`, `PATCH`, and `DELETE` requests. There is no wildcard origin, and no
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

The backend recognizes an authenticated Supabase user, and the profile and conversation endpoints
require that identity through `require_authenticated_user`. `app/auth.py` owns the boundary:

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
def example(user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)]) -> ...:
    ...
```

Failures are explicit and safe (Task 2.2 error shape, no provider text):

| Case | Status | Body |
| --- | --- | --- |
| No `Authorization` header | `401` | `{"detail": "Authentication required."}` + `WWW-Authenticate: Bearer` |
| Header is not a Bearer token | `401` | `{"detail": "The Authorization header must be a Bearer token."}` + `WWW-Authenticate: Bearer` |
| Token rejected (`invalid`, expired, unknown) | `401` | `{"detail": "Authentication credentials are invalid or expired."}` + `WWW-Authenticate: Bearer` |
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

`GET /me` is the endpoint that proves the identity → profile bridge: it requires a valid authenticated
user (`require_authenticated_user`), resolves that user's profile, and returns
`{user_id, created_at, updated_at}` — no tokens, passwords, credentials, or database internals. Identity
never comes from the request body or query.

| Case | Status | Body |
| --- | --- | --- |
| No / malformed / rejected token | `401` | (as in `## Authentication` above) |
| Supabase unconfigured or unreachable | `503` | `{"detail": "Authentication is temporarily unavailable."}` |
| Verified identity with no profile row | `500` | `{"detail": "The authenticated profile is unavailable."}` (a data-integrity signal, deliberately not a `404` callers could probe) |

## Conversations

`public.conversations` is the persistent conversation record — one row per user-owned conversation,
keyed by a database-generated UUID, with `user_id uuid not null references public.profiles (id) on
delete cascade` so the chain `auth.users → profiles → conversations` is explicit and a conversation
can never name an arbitrary UUID. `title` is nullable with no default (no AI titles yet);
`created_at`/`updated_at` are database-managed (`now()` defaults plus a before-update trigger
mirroring migration 0001). The owner query pattern is indexed (`conversations_user_id_idx`) — no
other indexes. RLS is enabled with four fail-closed policies, each scoped to `auth.uid() = user_id`;
the `insert` (and `update`) policy gates the written row with `with check`, so forged ownership is
rejected by the database. The schema lives in
[`supabase/migrations/0002_create_conversations.sql`](../../supabase/migrations/0002_create_conversations.sql);
`app/conversations.py` holds the `Conversation` row type plus the stores the endpoints need:
`SupabaseConversationStore.create` (the write) and the owner-scoped reads `list_for_user` and
`get_for_user`, plus the owner-scoped `rename_for_user` and `delete_for_user` writes.

`POST /conversations` creates one conversation for the verified caller and returns it with `201`.
It requires authentication (`require_authenticated_user`); the body is `{title?}` only — there is
no `user_id` field, so a forged owner id in the body is dropped by validation before the handler
runs. Titles are optional, trimmed, blank-becomes-`None`, and capped at 200 characters (`422` past
the limit). The store inserts exactly `(user_id, title)` through the service-role client and reads
the row back; the RLS `insert` policy remains the final boundary.

| Case | Status | Body |
| --- | --- | --- |
| No / malformed / rejected token | `401` | (as in `## Authentication` above) |
| Overlong or mistyped title | `422` | FastAPI validation error |
| Supabase unconfigured, unreachable, or empty insert result | `503` | `{"detail": "The conversation could not be created."}` |

`GET /conversations` returns the verified caller's conversations wrapped as `{"items": [...]}`, most
recently updated first with `id` descending as the tiebreak so the order is deterministic; an account
with none returns `200` with an empty `items` list. `GET /conversations/{conversation_id}` returns one
conversation the caller owns. Both endpoints require authentication, and both scope the query to the
verified `user_id` in the database — the path id is never proof of ownership. A conversation belonging
to someone else therefore answers exactly like one that does not exist (`404` with
`{"detail": "Conversation not found."}`), so a caller cannot probe for other users' conversations. The
path id must be a UUID (`422` before any query runs).

| Case | Status | Body |
| --- | --- | --- |
| No / malformed / rejected token | `401` | (as in `## Authentication` above) |
| Id that is not a UUID | `422` | FastAPI validation error |
| Missing conversation, or one owned by someone else | `404` | `{"detail": "Conversation not found."}` |
| Supabase unconfigured or unreachable (list) | `503` | `{"detail": "The conversations could not be read."}` |
| Supabase unconfigured or unreachable (single read) | `503` | `{"detail": "The conversation could not be read."}` |

`PATCH /conversations/{conversation_id}` renames one conversation the caller owns. The body is
`{"title": ...}` only — the same title rules as creation (trimmed, blank/`null` clears it, 200
characters max, `422` past the limit), and a forged `user_id` is dropped exactly as on `POST`. It
returns the updated conversation with `200`; `updated_at` is refreshed by the database's
before-update trigger, never written by the application. Ownership is enforced the same way as the
reads: the update statement filters on the verified `user_id` together with the id, so a foreign id
matches nothing and answers the identical `404`.

`DELETE /conversations/{conversation_id}` removes one conversation the caller owns and answers
`204 No Content` on success, with the same owner-scoped statement and the same indistinguishable
`404` for missing or foreign ids.

| Case | Status | Body |
| --- | --- | --- |
| No / malformed / rejected token | `401` | (as in `## Authentication` above) |
| Id that is not a UUID | `422` | FastAPI validation error |
| Rename without a valid `title` (missing, mistyped, overlong) | `422` | FastAPI validation error |
| Missing conversation, or one owned by someone else | `404` | `{"detail": "Conversation not found."}` |
| Supabase unconfigured or unreachable (rename) | `503` | `{"detail": "The conversation could not be updated."}` |
| Supabase unconfigured or unreachable (delete) | `503` | `{"detail": "The conversation could not be deleted."}` |

No message, chat, or runtime endpoint exists yet.

## Structure

```text
apps/api/
├── app/
│   ├── __init__.py
│   ├── auth.py           # authenticated-identity boundary (verified token → user)
│   ├── config.py         # centralized settings (AGENTSCHAT_API_*)
│   ├── conversations.py  # conversation row type + create/list/get/rename/delete stores (Tasks 5.2–5.4)
│   ├── logging_config.py # central logging setup (stdlib only, LOG_FORMAT)
│   ├── profiles.py       # profile store + lookup (verified identity → profile row)
│   ├── supabase_client.py # backend Supabase boundary (service-role key, server-only)
│   └── main.py           # FastAPI app: health, /me, and the conversation routes
├── tests/
│   ├── test_auth.py
│   ├── test_config.py
│   ├── test_conversation_creation.py
│   ├── test_conversation_retrieval.py
│   ├── test_conversations.py
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
