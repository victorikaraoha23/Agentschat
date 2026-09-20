# Progress

## Status summary

| Area | State |
|---|---|
| Monorepo scaffolding (`.gitignore`, `.editorconfig`, `README.md`) | ✅ done |
| Conventions (`CONVENTIONS.md` / `CLAUDE.md`) | ✅ done |
| Project context docs (`Agents.md`, `memory-bank/`) | ✅ done |
| Backend scaffold (uv project, `src/` tree, `/health`, health test, tooling) | ✅ done |
| Backend features (api, models, repositories, services) | ⬜ not started |
| Database schema + migrations + RLS | ⬜ not started |
| Credit service / ledger | ⬜ not started |
| LLM gateway + BYOK | ⬜ not started |
| Worker + recovery tasks | ⬜ not started |
| 7 pipeline stages + verification gates | ⬜ not started |
| Job trigger (confirm card) + completion posting | ⬜ not started |
| Revisions and the failure/recovery split | ⬜ not started |
| Billing / integrations | ⬜ not started |
| Frontend application | ⬜ not started |
| Test suites (beyond `tests/test_health.py`) | ⬜ not started |
| CI configuration | ⬜ not started |

**The backend is runnable. The frontend is not scaffolded and no product feature exists yet.**

## What works

- Git history on `main`; latest commit `df1fa97` ("feat(backend): scaffold FastAPI application").
- `.gitignore` covers Python, Node, env, testing, IDE, OS, and log artifacts — verified with
  `git check-ignore` against one representative path per pattern.
- `.editorconfig` pins UTF-8, LF, 2-space indent (4 for Python), no trailing whitespace, and exempts
  Markdown from whitespace trimming.
- `CONVENTIONS.md`, `CLAUDE.md`, and `.clinerules` are byte-identical (verified by SHA-256), so every
  tool reads the same rules.
- **Backend scaffold**: uv project on CPython 3.11 with a project-local venv (`backend/.venv`,
  gitignored) and a committed `uv.lock`; ruff, mypy (`strict = true` + the pydantic plugin), and
  pytest configured in `pyproject.toml`.
- **Backend runs**: `uv run pytest` passes, `uv run ruff check .` is clean, `uv run mypy src` is
  clean across 12 modules, and `uv run uvicorn src.main:app` serves `GET /health` →
  `{"status": "ok", "service": "agentschat-api"}`.
- `frontend/` exists as a `.gitkeep` placeholder only.

## What does not work yet

| Missing | Consequence |
|---|---|
| `frontend/package.json` | `npm run test:ci`, `typecheck`, and `lint` cannot run |
| `alembic.ini` + `alembic/` | `alembic upgrade head` cannot run; no schema or RLS policies exist |
| `tests/conftest.py` + fixtures | No DB-backed or async test can be written yet |
| Product routes and services | Only `/health` exists — no chat, job, credit, or billing surface |
| CI config | Nothing is enforced on push |

## Known gaps and risks

| Gap | Why it matters |
|---|---|
| No migrations exist yet | §4.6 requires RLS on every table — far easier to enforce from the first migration than to retrofit |
| No credit service | Every later feature spends credits; the ledger contract should land before anything charges |
| Backend is not packaged (no `[build-system]`) | `src.*` resolves from the working directory, so `uv run` must be invoked from `backend/`; a root-level or alternate-cwd invocation breaks imports |
| `src/config.py` holds only `database_url` | It must stay the ONLY place env vars are read; every new setting goes here, not into services |
| No `.gitattributes` | Line-ending normalization depends on local `core.autocrlf=true` (worktree CRLF, repo LF) rather than a committed policy |

## Suggested build order — proposal, not a commitment

1. Foundations: config, db, app skeleton, Alembic, test harness
2. Auth + workspaces + workspace balances
3. Credits: `credit_service`, reserve/release, ledger, trial grant
4. Chat layer: conversations, messages, streaming, `agent_execution_service`
5. Worker: slots, claim functions, recovery tasks
6. LLM gateway wiring + BYOK
7. Pipeline: `types.py`, `executor.py`, verification gates, the 7 stage handlers
8. Job trigger (confirm card) + completion posted back into chat
9. Revisions + the failure/recovery split
10. Billing (Lemon Squeezy) + integrations
11. Frontend surfaces
12. Hardening

## Verification log

| Date | What was verified | How |
|---|---|---|
| 2026-09-20 | Monorepo structure, conventions, `.gitignore` behaviour | `git ls-tree`, `git check-ignore`, SHA-256 hash comparison of `CONVENTIONS.md` vs `CLAUDE.md` |
| 2026-09-20 | `memory-bank/` created and referenced from `README.md` | file reads + `git status` |
| 2026-09-20 | Backend scaffold (commit `df1fa97`) | `uv run pytest` (1 passed), `uv run ruff check .` (clean), `uv run mypy src` (12 files, strict, clean), live `uvicorn` + `GET /health` → 200 with the exact body |
| 2026-09-20 | Backend venv is real and in use | `uv run python -c "import sys; print(sys.prefix)"` → `backend\.venv`; `uv pip list` confirms the project is *not* installed into it; `.venv` / `.pytest_cache` / `.coverage` are ignored while `uv.lock` / `pyproject.toml` are tracked |
