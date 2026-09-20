# Tech Context

## Current repository state (verified at `0890c0c`)

```
agentschat/
├── .editorconfig          # UTF-8, LF, indent 2 (4 for Python), no trailing whitespace
├── .gitignore             # Python, Node, env, testing, IDE, OS, logs
├── README.md              # one-liner + structure
├── CONVENTIONS.md         # backend + frontend rules
├── CLAUDE.md              # byte-identical copy of CONVENTIONS.md
├── Agents.md              # full project context — UNTRACKED as of 0890c0c
├── memory-bank/           # this persistent-context set
├── backend/               # placeholder only (.gitkeep) — no code yet
└── frontend/              # placeholder only (.gitkeep) — no code yet
```

There is **no application code, no dependency manifest, and no test suite**. Nothing here is
executable yet. The layout in `Agents.md` §3 is the target, not the current state.

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

Backend, from `backend/`:

```
pytest
mypy --strict src
ruff check .
alembic upgrade head          # then: downgrade -1, upgrade head
```

Frontend, from `frontend/`:

```
npm run test:ci
npm run typecheck             # tsc --noEmit
npm run lint
```

> None of these run today: there is no `pyproject.toml` and no `package.json`.

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
