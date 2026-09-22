# Active Context

- **Date:** 2026-09-22 (Task 1.2 session). Checkout branch `update`.
- **Current task:** Task 1.2 (web structure and conventions) — complete. Task 1.3 **not** started.
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
  - Repository reality: this checkout **is** the Hermes source tree (runtime vendored in-tree). `web/` is the
    Hermes dashboard SPA and `apps/` holds the Hermes desktop/shared/bootstrap-installer packages. AgentsChat
    application code lives in `apps/web` (added in Task 1.1); `apps/api` does not exist yet.
  - **Task 1.1 (2026-09-22):** `apps/web` initialized (Next `16.3.5`, React `19.2.8`, App Router,
    TypeScript strict, ESLint, no Tailwind) with a single static page naming AgentsChat. Independent npm
    package `agentschat-web` installed via `npm install --workspaces=false`. No API, auth, chat, Supabase or
    Hermes integration exists.
  - **Task 1.2 (2026-09-22):** reviewed the web structure and kept it as-is (already minimal and correct);
    documented conventions in `apps/web/README.md` (routes/layouts, server-first components, styling,
    future `components/` and `lib/` locations, `@/*` alias, strict TS, file naming). No new directories,
    configuration, or dependencies.
- **Open questions / pending user input:**
  - The root `package.json` npm workspace glob (`apps/*`) still matches `apps/web`. Task 1.1 decided the app is
    an independent package (`npm install --workspaces=false`); narrowing the glob remains an explicitly scoped
    Hermes change and is not planned inside any AgentsChat task so far.
  - Should `pyproject.toml`'s `readme = "README.md"` be repointed to `docs/hermes-runtime.md` (moved
    Hermes README), and should `apps/desktop/README.md`'s `../../README.md` link follow it?
- **Next steps:**
  - Start Task 1.3 only on explicit instruction; read the root `AGENTS.md` and `apps/web/README.md` first.
  - On code changes: `scripts/run_tests.sh` for Hermes source; keep prompt-caching and profile-scope
    invariants.
- **Key files for orientation:** `AGENTS.md` → `README.md` → `docs/hermes-runtime.md` → `memory-bank/*`;
  `SOUL.md` (tone); `pyproject.toml` (pins/env); `package.json` (npm workspaces).
