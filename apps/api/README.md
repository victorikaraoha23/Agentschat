# AgentsChat API

The FastAPI backend/API for AgentsChat. **Foundation stage:** it starts locally and exposes a health
check, the authentication boundary, the `GET /me` profile read, and the conversation endpoints —
`POST /conversations`, `GET /conversations`, `GET /conversations/{conversation_id}`,
`PATCH /conversations/{conversation_id}`, and `DELETE /conversations/{conversation_id}` — all backed by
Supabase — plus `POST /conversations/{conversation_id}/messages` for persisting user messages and
`POST /conversations/{conversation_id}/execute` for submitting one to the agent runtime, which persists
both the user's message and the assistant's reply. An
agent-runtime boundary (`app/runtime.py`: `RuntimeRequest`, `RuntimeResult`, `AgentRuntime`,
`get_agent_runtime`) has a Hermes adapter (`app/hermes_adapter.py`) behind it, and execution is a
single synchronous request/response run — no assistant message is persisted yet and nothing is
streamed. No Hermes process or credentials are required unless `AGENTSCHAT_API_HERMES_EXECUTABLE` is
explicitly configured.

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
| `AGENTSCHAT_API_HERMES_EXECUTABLE` | *(unset)* | Command or path that starts the Hermes CLI; unset keeps Hermes unconfigured and agent runs report `unavailable`. An entry that is present but blank fails validation |
| `AGENTSCHAT_API_HERMES_TIMEOUT_SECONDS` | `120` | Hard wall-clock limit for one agent run; the run is stopped and reported as timed out when it elapses; must be greater than zero |

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

Assistant message persistence, message-history retrieval, and streaming do not exist yet: see
`## Execution` below for what does run.

## Execution (Tasks 8.1 and 8.2)

`POST /conversations/{conversation_id}/execute` is the first real execution path — the one place a
user message travels `FastAPI → runtime interface → Hermes adapter → Hermes`. The body is
`{"content": "..."}` only: the same `CreateMessageRequest` model the message endpoint uses, so
validation is identical (missing, empty, whitespace-only, or content past 4000 characters is the same
`422`). No model, provider, temperature, tools, files, or other runtime configuration is
client-settable.

The handler performs exactly this sequence, in this order:

1. authenticate (the Task 3.2 dependency — identity never comes from the body or path);
2. persist the user message through the same owner-scoped store as `POST .../messages`, which is also
   the ownership check: a conversation the caller does not own writes nothing and answers the same
   `404` as one that does not exist, so the runtime is never reached for it;
3. build a `RuntimeRequest` from the persisted row — `user_id`, `conversation_id`, `content` only —
   with no HTTP request, Supabase client, credential, or Hermes object crossing the boundary;
4. `await runtime.execute(request)` exactly once: no retry, no queue, no background worker;
5. on success, persist the reply as an `assistant` message in the same conversation (Task 8.2), owned by
   the caller's verified identity;
6. answer with the completed execution and the persisted reply's id.

Success answers `200` with `ExecutionResponse` — `{"status": "completed", "content": "...",
"message_id": "..."}` — because the caller needs the identity of the row that was stored, not the raw
runtime result. `content` is exactly what was persisted. Failures are HTTP errors whose `detail` is
always fixed application wording, never `RuntimeResult.message`:

| Runtime reason | Status | `detail` |
| --- | --- | --- |
| `unavailable` | `503` | The agent runtime is not available. |
| `failed` | `502` | The agent run failed. |
| `timed-out` | `504` | The agent run took too long and was stopped. |
| `invalid-request` | `400` | The agent runtime rejected the request. |

| Case | Status | Body |
| --- | --- | --- |
| No / malformed / rejected token | `401` | (as in `## Authentication` above) |
| Id that is not a UUID | `422` | FastAPI validation error |
| Missing, empty, whitespace-only, or overlong content | `422` | FastAPI validation error |
| Missing conversation, or one owned by someone else | `404` | `{"detail": "Conversation not found."}` |
| Supabase unconfigured or unreachable while persisting the request | `503` | `{"detail": "The message could not be sent."}` |
| Runtime failure (table above) | `502` / `503` / `504` / `400` | `{"detail": "<fixed wording>"}` |
| The reply itself could not be stored | `503` | `{"detail": "The agent reply could not be saved."}` |

**Failure semantics.** The user message is persisted *before* the run starts, so when the runtime
fails the conversation still holds the user's request: nothing is deleted, no assistant message is
invented, and nothing is retried. Exactly one run happens per HTTP request; full execution
idempotency for a client that submits the same request twice is deliberately **deferred** — there is
no lock, queue, or deduplication store, and introducing one is not part of this task.

A run that succeeded but whose reply cannot be stored answers `503`, not a success. Reporting
completion would leave the user's message in the conversation with no reply and nothing indicating
that anything went wrong; the run itself is not retried, so the client decides what to do next.

Tests swap a fake runtime in through `get_agent_runtime`, so the normal suite never starts Hermes.
`tests/test_execute_endpoint.py` covers authentication, ownership, validation, persistence order,
each failure translation, and leak resistance; `tests/test_assistant_persistence.py` covers what
happens to the reply afterwards.

## Streamed execution (Task 8.3)

`POST /conversations/{conversation_id}/execute/stream` answers Server-Sent Events instead of one JSON
body, so the reply can be shown as it is produced. The transport is SSE rather than WebSockets
because the request is a POST with a JSON body and an `Authorization` header, which the browser's
`EventSource` cannot send; the client reads a `fetch` response body and parses the framing. Nothing
else was introduced: the stream runs inside the normal FastAPI request lifecycle, with no queue, no
broker, and no background worker.

Everything before the first byte of the stream is identical to the buffered endpoint -- the same
body model, the same verified identity, and the same owner-scoped user-message write that is also the
ownership check. Those steps run first, so an unauthenticated caller, a foreign conversation, and
invalid content are still ordinary HTTP errors rather than a stream that fails after it opens.

The protocol starts with the persisted user row, then carries deltas and one terminal event:

```
event: start
data: {"message":{"id":"...","conversation_id":"...","user_id":"...","role":"user","content":"Hi","created_at":"..."}}

event: delta
data: {"content":"Hello"}

event: complete
data: {"message_id":"...","content":"Hello","message":{"id":"...","conversation_id":"...","user_id":"...","role":"assistant","content":"Hello","created_at":"..."}}

event: error
data: {"code":"failed","message":"The agent run failed."}
```

The `complete` content and message metadata come from the stored assistant row. Runtime cleanup
and persistence finish before completion is emitted. A runtime exception or missing terminal event
produces a fixed `error`; disconnects close the response body and runtime stream.

Payloads are JSON, so a reply containing newlines cannot break the framing. The `code` values are the
runtime contract's `RuntimeFailureReason`, plus `assistant-persist-failed` and `not-found` for the two
failures that belong to this endpoint. Only fixed application wording is ever sent: Hermes event
records, exit codes, and error text stay server-side.

**Persistence.** The user's message is stored before the run starts. Deltas are forwarded and
accumulated in memory, but **nothing is written until the run completes**: a run that fails half way
has produced text that is not an answer, and the database represents completed responses only. The
single terminal event decides everything -- `complete` means exactly one assistant message was stored,
`error` means none was.

**Cancellation.** A browser disconnect closes the stream, which ends the adapter's generator, whose
`finally` terminates the child process. No detached task keeps reading Hermes, and nothing is stored
for a reply nobody received.

The Hermes adapter reads the child's stdout a line at a time instead of waiting for it to exit, so
each `text` record becomes a delta immediately. Only `text` records are forwarded; `system`,
`tool_use`, `tool_result`, and `result` stay inside the adapter, and the terminal `result` record is
what decides success or failure -- exactly as in the buffered path.

## Assistant messages (Task 8.2)

`public.messages.role` accepts `user` and `assistant` (migration `0004`). Assistant rows are written
only by the server, through `SupabaseMessageStore.create_assistant_for_user`, which passes through the
same owner-scoped conversation read as the user write — so an assistant row can only ever land in a
conversation the authenticated caller owns. `system`, `tool`, `function`, and `agent` remain refused
by the database check until a real code path exists to produce them.

No client can request an assistant row: `CreateMessageRequest` has no `role` field, and the endpoints
pass a module constant rather than anything from the request. The reply's content is stored exactly as
the runtime produced it — no truncation, no appended metadata, no Hermes text — and the runtime never
decides ownership, only text.

## Agent runtime boundary (Tasks 7.1–7.2)

`app/runtime.py` defines the application-level boundary that the Hermes adapter sits behind, so
application code depends on the contract rather than on Hermes imports, config keys, or response
shapes (`API/domain → runtime interface → Hermes adapter → Hermes`):

| Piece | Purpose |
| --- | --- |
| `RuntimeRequest` | The smallest useful execution input: verified `user_id`, `conversation_id`, and trimmed non-blank `content` (4000 characters max, mirroring the message endpoint). Never shell commands, code, paths, or credentials. |
| `RuntimeResult` | Stable outcome: `ok=True` with assistant `output`, or `ok=False` with one small `RuntimeFailureReason` (`unavailable`, `failed`, `timed-out`, `invalid-request`) and a safe summary. Never exceptions, tracebacks, subprocess details, paths, or secrets. |
| `AgentRuntime` | Async `execute(request) -> result` protocol, so the adapter may do model calls, subprocess, or network work correctly without new infrastructure. |
| `get_agent_runtime` / `AgentRuntimeDep` | FastAPI dependency returning the configured implementation — `HermesRuntimeAdapter` when `AGENTSCHAT_API_HERMES_EXECUTABLE` is set, otherwise an unavailable-runtime placeholder — so `dependency_overrides` can substitute fakes without touching business logic. |

`tests/fake_runtime.py` provides the in-memory doubles (`FakeSuccessRuntime`, `FakeFailureRuntime`:
no Hermes, model, subprocess, or network) and `tests/test_runtime_contract.py` proves the request/result
shapes, both fake outcomes, the DI substitution, and the default unavailable answer.

### Hermes adapter (Task 7.2)

`app/hermes_adapter.py` is the only module that knows how to reach Hermes, and it reaches it through
Hermes's documented, machine-readable CLI surface in a child process — it never imports Hermes. One run:

1. writes the request's `content` to a query file inside a **fresh temporary workspace**;
2. starts `<executable> chat --query-file <path> --format stream-json --oneshot` with that workspace as
   the working directory, a **filtered environment** with every `AGENTSCHAT_*` variable removed, and
   `asyncio.create_subprocess_exec` (no shell), under `AGENTSCHAT_API_HERMES_TIMEOUT_SECONDS`;
3. parses the terminal `result` record of the stream-JSON output and maps it onto `RuntimeResult`.

Consequences worth knowing:

- **User text is never a command-line argument**, so quotes, `$(...)`, and backticks cannot become
  arguments or shell syntax.
- **The runtime never sees this application's directory, its configuration, or the service-role key.**
- **Timeouts stop the child** (terminate, then kill) and report `timed-out`; a command that cannot be
  started reports `unavailable`; a bad exit code, a Hermes `error` field, missing output, or unparseable
  output reports `failed`.
- **Hermes's own wording never reaches a caller.** Callers get one of three fixed summaries; exit codes,
  Hermes error text, and the stderr tail are logged server-side only.

Conversation continuity across runs (resuming a Hermes session per `conversation_id`) is deliberately
**not** part of this task: the run's workspace is disposable, so no session survives it. That belongs
with the durable per-run workspace and is recorded as a follow-up.

The execution endpoint above is the adapter's only caller: a run happens only inside an
authenticated `POST .../execute` request, and startup and `GET /health` still never touch Hermes.

## Structure

```text
apps/api/
├── app/
│   ├── __init__.py
│   ├── auth.py           # authenticated-identity boundary (verified token → user)
│   ├── config.py         # centralized settings (AGENTSCHAT_API_*)
│   ├── conversations.py  # conversation row type + create/list/get/rename/delete stores (Tasks 5.2–5.4)
│   ├── hermes_adapter.py # Hermes CLI adapter behind the runtime contract (Task 7.2)
│   ├── logging_config.py # central logging setup (stdlib only, LOG_FORMAT)
│   ├── messages.py       # message row type + create store (Task 6.2)
│   ├── profiles.py       # profile store + lookup (verified identity → profile row)
│   ├── runtime.py        # agent runtime contract: request/result types, AgentRuntime, DI (Task 7.1)
│   ├── supabase_client.py # backend Supabase boundary (service-role key, server-only)
│   └── main.py           # FastAPI app: health, /me, conversations, messages, execution
├── tests/
│   ├── test_auth.py
│   ├── test_config.py
│   ├── test_conversation_creation.py
│   ├── test_conversation_retrieval.py
│   ├── test_conversations.py
│   ├── test_cors.py
│   ├── test_error_handling.py
│   ├── test_execute_endpoint.py # execution endpoint: auth, ownership, persistence order, failures
│   ├── test_assistant_persistence.py # assistant reply: persistence, ownership, failure semantics
│   ├── test_health.py
│   ├── test_hermes_adapter.py   # command shape, isolation, outcome translation, DI selection
│   ├── test_logging.py
│   ├── test_message_creation.py
│   ├── test_message_store.py
│   ├── test_messages.py
│   ├── test_profiles.py
│   ├── test_runtime_contract.py
│   ├── fake_runtime.py     # in-memory AgentRuntime doubles (success + failure)
│   └── test_supabase.py
├── .env.example         # documents AGENTSCHAT_API_SUPABASE_* and AGENTSCHAT_API_HERMES_* (placeholders only, committable)
├── pyproject.toml       # dependencies + pytest configuration
└── uv.lock              # locked dependency versions
```

## Notes

- This is an **independent project** with its own `pyproject.toml`, `.venv`, and `uv.lock`. It is not part
  of the Hermes root Python package or the Hermes virtualenv — install and run it from inside `apps/api/`.
- The Hermes root `[tool.setuptools.packages.find]` include list does not cover `apps/`, so these files
  are never swept into the Hermes wheel, and the Hermes root pytest `testpaths = ["tests"]` does not
  collect `apps/api/tests`.
