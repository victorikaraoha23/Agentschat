# Progress

## Status summary

| Area | State |
|---|---|
| Monorepo scaffolding (`.gitignore`, `.editorconfig`, `README.md`) | ✅ done |
| Conventions (`CONVENTIONS.md` / `CLAUDE.md`) | ✅ done |
| Project context docs (`Agents.md`, `memory-bank/`) | ✅ done |
| Backend application code | ⬜ not started |
| Database schema + migrations + RLS | ⬜ not started |
| Credit service / ledger | ⬜ not started |
| LLM gateway + BYOK | ⬜ not started |
| Worker + recovery tasks | ⬜ not started |
| 7 pipeline stages + verification gates | ⬜ not started |
| Job trigger (confirm card) + completion posting | ⬜ not started |
| Revisions and the failure/recovery split | ⬜ not started |
| Billing / integrations | ⬜ not started |
| Frontend application | ⬜ not started |
| Test suites | ⬜ not started |
| CI configuration | ⬜ not started |

**Nothing in this repository is executable yet.**

## What works

- Git history is initialized on `main` at `0890c0c` ("chore: initialize monorepo with conventions").
- `.gitignore` covers Python, Node, env, testing, IDE, OS, and log artifacts — verified with
  `git check-ignore` against one representative path per pattern.
- `.editorconfig` pins UTF-8, LF, 2-space indent (4 for Python), no trailing whitespace, and exempts
  Markdown from whitespace trimming.
- `CONVENTIONS.md` and `CLAUDE.md` are byte-identical (verified by hash), so every tool reads the
  same rules.
- `backend/` and `frontend/` exist as `.gitkeep` placeholders, so the intended structure is
  reproducible from a clone.

## What does not work yet

| Missing | Consequence |
|---|---|
| `backend/pyproject.toml` | `pytest`, `mypy`, `ruff`, and `alembic` cannot run |
| `frontend/package.json` | `npm run test:ci`, `typecheck`, and `lint` cannot run |
| Any `src/` module | The app cannot start; no routes exist |
| Any migration | No schema, no RLS policies |
| CI config | Nothing is enforced on push |

## Known gaps and risks

| Gap | Why it matters |
|---|---|
| No migrations exist yet | §4.6 requires RLS on every table — far easier to enforce from the first migration than to retrofit |
| No credit service | Every later feature spends credits; the ledger contract should land before anything charges |
| `Agents.md` is untracked | The authoritative context document is not in version control, so a fresh clone loses it |
| No `.gitattributes` | Line-ending normalization depends on local `core.autocrlf=true` (worktree CRLF, repo LF) rather than a committed policy |
| No secrets/config story on disk yet | `src/config.py` must become the single source of env vars before any service reads one |

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
