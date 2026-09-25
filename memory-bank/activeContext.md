# Active Context

- **Date:** 2026-09-22 (Task 2.2 session: error-handling foundation). Checkout branch `update`.
- **Current task:** Task 2.2 (error-handling foundation) — complete. Task 2.3 **not** started.
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
    application code lives in `apps/web` (Task 1.1) and `apps/api` (Task 1.3).
  - **Task 1.1 (2026-09-22):** `apps/web` initialized (Next `16.3.5`, React `19.2.8`, App Router,
    TypeScript strict, ESLint, no Tailwind) with a single static page naming AgentsChat. Independent npm
    package `agentschat-web` installed via `npm install --workspaces=false`. No API, auth, chat, Supabase or
    Hermes integration exists.
  - **Task 1.2 (2026-09-22):** reviewed the web structure and kept it as-is (already minimal and correct);
    documented conventions in `apps/web/README.md` (routes/layouts, server-first components, styling,
    future `components/` and `lib/` locations, `@/*` alias, strict TS, file naming). No new directories,
    configuration, or dependencies.
  - **Task 1.3 (2026-09-22):** `apps/api` created as an independent `uv` project (own `pyproject.toml`,
    `uv.lock`, `.venv`; Python `>=3.11,<3.14`; FastAPI + uvicorn, pytest + httpx dev group) with
    `app/main.py` exposing typed `GET /health` (`HealthResponse`, exact body `{"status": "healthy"}`) and
    `tests/test_health.py` via FastAPI's `TestClient`; app-local README documents install/run/test.
    No auth, database, CORS, exception handlers, logging, or Hermes integration; root `README.md`
    status/layout/roadmap/env sections updated.
  - **Ad-hoc (2026-09-22):** Vercel readiness for `apps/web` — proved plain `npm install` from `apps/web`
    climbs into the Hermes workspace root; added `apps/web/vercel.json` pinning
    `installCommand: npm install --workspaces=false`, documented Root Directory = `apps/web` in the app
    README, and corrected the root README's deployment claim. Not a roadmap task.
  - **Task 1.4 (2026-09-22):** centralized API settings in `apps/api/app/config.py` (`pydantic-settings`,
    `AGENTSCHAT_API_` prefix; `app_name` + `environment` only) wired into `FastAPI(title=...)`;
    `/health` unchanged; 5 config tests added (6 total pass). No `.env.example` — no secrets exist yet;
    variables documented in `apps/api/README.md`.
  - **Task 1.5 (2026-09-22):** the browser now calls the API. `apps/web/app/health-api.ts` (typed,
    never-throwing result union, injected `fetch` seam) + `app/health-api.test.ts` (Node's built-in
    `node --test`, 5 tests) + `"use client"` `page.tsx` showing frontend/checking/succeeded/failed states
    with `aria-live`; single optional `NEXT_PUBLIC_API_URL` (default `http://127.0.0.1:8000`) documented in
    `apps/web/.env.example`; API gained `CORSMiddleware` with a two-origin dev allowlist for `GET`
    (`apps/api/app/main.py`, `DEV_ALLOWED_ORIGINS`) plus `tests/test_cors.py`; `tsconfig.json` gained
    `allowImportingTsExtensions` for the native test runner. No auth, database, chat, or Hermes work.
  - **Ad-hoc (2026-09-22):** Vercel **Web Analytics + Speed Insights** wired into the web root layout
    (`@vercel/analytics` 2.0.1, `@vercel/speed-insights` 2.0.0, exact pins; lockfile updated) on explicit
    owner request. No server, secret, environment variable, or new service: the client components inject
    Vercel's own platform-served scripts and only report on a Vercel deployment. Consent/privacy handling
    deferred. Recorded against `AGENTS.md` §4 (monitoring needs a stated requirement) and §17.
  - **Task 2.1 (2026-09-22, earlier session):** `fix(web)` added a five-second API health-check timeout in
    `apps/web/app/health-api.ts` (AbortController, timeout classified as a `network` failure) with two extra
    tests; `test(api)` isolated the unprefixed-settings test from ambient environment variables.
  - **Task 2.2 (2026-09-22):** error-handling foundation. Backend: `unhandled_exception_handler` in
    `app/main.py` (`app.add_exception_handler(Exception, ...)`) answers unexpected exceptions with a fixed
    `{"detail": "Internal server error."}` JSON 500; expected errors keep FastAPI's `{"detail": ...}` shape;
    `/health` unchanged; new `tests/test_error_handling.py` (5 tests, incl. leak assertions). Frontend: an
    `unexpected` failure category with a fixed message added to `HealthCheckResult`, plus its test. Docs:
    API `## Errors` section, web failure-category wording, `apps/api/README.md` structure.
- **Open questions / pending user input:**
  - The root `package.json` npm workspace glob (`apps/*`) still matches `apps/web`. Task 1.1 decided the app is
    an independent package (`npm install --workspaces=false`); narrowing the glob remains an explicitly scoped
    Hermes change and is not planned inside any AgentsChat task so far.
  - Should `pyproject.toml`'s `readme = "README.md"` be repointed to `docs/hermes-runtime.md` (moved
    Hermes README), and should `apps/desktop/README.md`'s `../../README.md` link follow it?
- **Next steps:**
  - Start Task 2.3 only on explicit instruction; read the root `AGENTS.md`, `apps/api/README.md`, and
    `apps/web/README.md` first.
  - On code changes: `scripts/run_tests.sh` for Hermes source; keep prompt-caching and profile-scope
    invariants.
- **Key files for orientation:** `AGENTS.md` → `README.md` → `docs/hermes-runtime.md` → `memory-bank/*`;
  `SOUL.md` (tone); `pyproject.toml` (pins/env); `package.json` (npm workspaces).
