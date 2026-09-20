# AgentsChat

A messenger-style web app where every conversation is with an AI agent: create agents, chat one-on-one, and trigger content-production jobs that run a deterministic 7-stage pipeline and post the finished deliverable back into the conversation.

## Repository structure

- `backend/` — FastAPI service, worker, 7-stage pipeline, migrations, tests
- `frontend/` — Next.js (App Router) UI, components, hooks
- `CONVENTIONS.md` — backend and frontend rules for contributors and coding agents
- `memory-bank/` — persistent context: brief, product, architecture, tech, active focus, progress
- `CLAUDE.md` — identical copy of `CONVENTIONS.md`

`CONVENTIONS.md` and `CLAUDE.md` are kept identical on purpose, so every tool sees the same rules.

## Development

Each app owns its own toolchain. The backend runs in a project-local Python virtual environment at
`backend/.venv`, managed by uv — see [`backend/README.md`](backend/README.md) for `uv sync`,
activation, and the test / lint / type-check commands.
