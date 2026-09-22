# Active Context

- **Date:** 2026-09-22 (Task 0.2 session). Checkout branch `update`.
- **Current task:** Task 1.1 (Next.js foundation in `apps/web`) — complete. Task 1.2 **not** started.
- **What was done:**
  - **Task 0.1 (2026-09-22):** rewrote root `AGENTS.md` as the AgentsChat engineering constitution
    (mission, separation of concerns, dependency direction, simplicity, atomic dev, type safety, API,
    database and RLS, auth vs authz, security, Hermes boundary, agent safety, error handling, testing,
    frontend, env vars, dependencies, code quality, git, documentation, no speculative features,
    10-point Definition of Done, Appendix A routing to Hermes area guides). Commit `5026704a4e`.
  - **Task 0.2 (2026-09-22):** root `README.md` now documents AgentsChat (status, planned architecture,
    atomic development principle, repository layout, roadmap, environment configuration); the upstream
    Hermes runtime README is preserved at `docs/hermes-runtime.md` (relative links rebased); `.gitignore`
    gained an AgentsChat section (Next.js output, Node logs, Python tooling artifacts, editors/OS,
    `.env.*.local`). No `apps/web`/`apps/api` directories, no `.env.example`, no dependencies, no tooling
    and no CI were added.
  - Repository reality: this checkout **is** the Hermes source tree (runtime vendored in-tree); AgentsChat
    application code does not exist yet. `web/` = Hermes dashboard SPA, `apps/` = Hermes desktop/shared/
    bootstrap-installer.
  - **Task 1.1 (2026-09-22):** `apps/web` initialized (Next `16.3.5`, React `19.2.8`, App Router,
    TypeScript strict, ESLint, no Tailwind) with a single static page naming AgentsChat. Independent npm
    package `agentschat-web` installed via `npm install --workspaces=false`. No API, auth, chat, Supabase or
    Hermes integration exists.
- **Open questions / pending user input:**
  - Should the root `package.json` npm workspace glob (`apps/*`) be scoped before `apps/web` is created?
  - Should `pyproject.toml`'s `readme = "README.md"` be repointed to `docs/hermes-runtime.md` (moved
    Hermes README), and should `apps/desktop/README.md`'s `../../README.md` link follow it?
- **Next steps:**
  - Start Task 1.2 only on explicit instruction; read the root `AGENTS.md` and `apps/web/README.md` first.
  - On code changes: `scripts/run_tests.sh` for Hermes source; keep prompt-caching and profile-scope
    invariants.
- **Key files for orientation:** `AGENTS.md` → `README.md` → `docs/hermes-runtime.md` → `memory-bank/*`;
  `SOUL.md` (tone); `pyproject.toml` (pins/env); `package.json` (npm workspaces).
