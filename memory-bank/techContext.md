# Tech Context

## Current repository state (verified at `df1fa97`)

```
agentschat/
├── .editorconfig          # UTF-8, LF, indent 2 (4 for Python), no trailing whitespace
├── .gitignore             # Python, Node, env, testing, IDE, OS, logs
├── README.md              # one-liner + structure + development pointer
├── CONVENTIONS.md         # backend + frontend rules
├── CLAUDE.md              # byte-identical copy of CONVENTIONS.md
├── Agents.md              # full project context (tracked since e1f126a)
├── .clinerules            # byte-identical copy of CONVENTIONS.md (IDE rules file)
├── memory-bank/           # this persistent-context set
├── backend/               # scaffolded — see below
└── frontend/              # placeholder only (.gitkeep) — no code yet
```

`backend/` in detail:

```
backend/
├── pyproject.toml         # deps, [dependency-groups] dev, ruff / mypy / pytest config
├── uv.lock                # committed lockfile
├── .python-version        # 3.11
├── README.md              # environment + commands
├── .venv/                 # CPython 3.11.16 venv via uv — GITIGNORED, never commit
├── src/
│   ├── main.py            # FastAPI app + GET /health
│   ├── config.py          # Settings (pydantic-settings) — the only env-var reader
│   ├── db.py              # engine, SessionLocal, get_db
│   ├── api/               # (each of these is still just an empty __init__.py)
│   ├── models/
│   ├── repositories/
│   ├── services/
│   ├── workflows/
│   ├── workflows/stages/
│   ├── tasks/
│   └── utils/
└── tests/
    ├── __init__.py
    └── test_health.py
```

The backend is runnable: the test suite, lint, type check, and the API server all pass. Everything
under `src/` except `main.py`, `config.py`, and `db.py` is still an empty package, and the frontend
is untouched. The layout in `Agents.md` §3 remains the target for both.

## Target stack

### Backend (`backend/`)

| Concern | Choice |
|---|---|
| Language | Python 3.11 — `mypy --strict` must pass |
| Web framework | FastAPI (`src/main.py`: app, lifespan, router includes) |
| ORM | SQLAlchemy 2.0 async — `from src import db`, call `db.SessionLocal()` at use time |
| Migrations | Alembic (`backend/alembic/`) |
| Config | `pydantic-settings` in `src/config.py` — the ONLY source of env vars |
| LLM | LiteLLM, isolated inside `src/services/llm.py` (`call_llm`, `stream_llm`) |
| Realtime | Redis Streams (`src/services/redis_streams.py`: publish / read / last_id) |
| Database | Postgres (Supabase). The public schema is exposed over PostgREST, so every table needs RLS enabled |
| Secrets | Supabase Vault wrapper (`src/services/vault.py`) + envelope encryption (`byok_service.py`) |
| Billing | Lemon Squeezy webhooks (`src/services/subscription_service.py`) |
| BYOK providers | OpenAI, Anthropic, Google |
| Lint / format | ruff |
| Tests | pytest in `backend/tests/`, mirroring the `src/` layout |

Worker: `src/worker.py`, `worker_concurrency` slots (default 4), plus periodic recovery tasks.
Deployment: Railway.

### Frontend (`frontend/`)

| Concern | Choice |
|---|---|
| Framework | Next.js App Router — server components by default |
| Language | TypeScript strict, no `any` |
| Forms | React Hook Form + Zod |
| Markdown | `react-markdown` + `rehype-sanitize` only |
| Streaming | `fetch` + `ReadableStream` (`lib/sse.ts`) — `EventSource` cannot send Authorization headers |
| API access | everything through `lib/api.ts` (`apiFetch`) |
| Tests | vitest + MSW (`frontend/test/msw/`); Playwright for happy paths only |

## Documented commands

The contracts to satisfy once the toolchains exist (`Agents.md` §13).

### Backend environment (venv)

Every backend command runs inside a project-local virtual environment at `backend/.venv`:

| Fact | Value |
|---|---|
| Interpreter | CPython 3.11.16 (uv-managed; `include-system-site-packages = false`) |
| Prompt | `agentschat-backend` |
| Tracked? | **No** — `.gitignore:9 .venv/` |
| Lockfile | `uv.lock`, committed |

```
uv sync                # create/refresh .venv (the `dev` group is a uv default group)
uv sync --no-dev       # runtime dependencies only
uv sync --locked       # CI: require uv.lock to be current, do not rewrite it
```

`uv run` uses `backend/.venv` automatically, so activating is optional. To activate explicitly use
`.\.venv\Scripts\Activate.ps1` (Windows) or `source .venv/bin/activate` (POSIX). To confirm which
interpreter is in use: `uv run python -c "import sys; print(sys.prefix)"`.

The project is **not packaged** — `pyproject.toml` declares no `[build-system]`, so nothing is
installed into `.venv` and `src.*` resolves from the working directory instead. Two consequences:

- Always invoke `uv run` from `backend/`.
- `from src import db` works because the project root lands on `sys.path` (pytest's prepend import
  mode via `tests/__init__.py`; uvicorn's `--app-dir` default of the cwd).

Backend commands, from `backend/` — **all verified working** at `df1fa97`:

```
uv run pytest                 # coverage comes from addopts = "--cov=src"
uv run ruff check .
uv run mypy src               # 12 modules, strict
uv run uvicorn src.main:app   # GET /health -> 200
uv run alembic upgrade head   # not runnable yet: no alembic.ini / alembic/ env exists
```

Frontend, from `frontend/`:

```
npm run test:ci
npm run typecheck             # tsc --noEmit
npm run lint
```

> The frontend commands cannot run yet: there is no `package.json`.

## Testing contract (`Agents.md` §4.7, §11)

Fixtures that must exist in `backend/tests/conftest.py`:

| Fixture | Use |
|---|---|
| `db` | every unit test; rolls back |
| `db_commit` | concurrency + worker tests; real commits, truncated after |
| `client` | httpx against the app with `db` overridden |
| `client_commit` | httpx with real sessions, for endpoint concurrency tests |
| `mock_llm` | deterministic LiteLLM — patches `litellm.acompletion`, `completion_cost`, `token_counter` |
| `mock_redis` | flushes Redis DB 15 |

Also required: `tests/factories.py`, `tests/concurrency.py` (`run_concurrent`), `tests/mocks/`.
No test may hit the network — the LLM is only ever reached through `mock_llm`.

Combined with the above, tests imply reachable Postgres and Redis (Redis DB 15 is reserved for
tests). The concrete local dev setup is still an open decision — see `activeContext.md`.

## Deployment and environment constraints

- Every client-exposed frontend env var **must** start with `NEXT_PUBLIC_`, or it is `undefined` in
  the browser.
- `RUN_MIGRATIONS=1` on exactly **one** Railway replica — never more.
- `src/config.py` is the only place env vars are read.

## Workstation facts

- Windows + PowerShell; git `core.autocrlf=true`, so the worktree is CRLF while the repo stores LF.
  This matches `.editorconfig` (`end_of_line = lf`). There is no committed `.gitattributes`, so line
  normalization depends on local config.
- Working branch `main`; remote `origin` = `https://github.com/victorikaraoha23/Agentschat.git`.
- Multiple shell commands launched in one batch may run concurrently — sequence dependent commands
  with `;` in a single command string.
