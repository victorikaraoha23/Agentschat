# Active Context

- **Date:** 2026-10-03 (Task 5.2 session: Conversation Creation). Checkout branch `update`.
- **Current task:** Task 5.2 (Conversation Creation) — implement `POST /conversations`.
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
  - **Task 2.3 (2026-09-25):** logging foundation — backend only, frontend deliberately unchanged (its one
    API-call module already reports typed failures with fixed UI text; nothing worth logging exists, and
    production console output stays quiet). New `apps/api/app/logging_config.py` (stdlib `logging` only:
    `configure_logging` + `LOG_FORMAT` timestamp/level/name/message, shared `agentschat` logger); new
    `AGENTSCHAT_API_LOG_LEVEL` setting (validated `Literal`, default `INFO`); `app/main.py` wires a
    `lifespan` (startup/shutdown `INFO` boundary logs, never per-request) and `logger.exception` in the
    generic-500 handler (traceback server-side only; request path/headers/body never logged). No request
    logging added — Uvicorn access logs already cover it. Tests: `tests/test_logging.py` (configure/format,
    app start, lifespan boundaries) + extended config/error tests; README `## Logging` section.
- **Task 3.3 (2026-10-02):** User Model — the identity bridge, no product data. New
    `supabase/migrations/0001_create_profiles.sql` (`public.profiles`: `id uuid primary key references
    auth.users (id) on delete cascade`, `created_at`/`updated_at` defaults; RLS enabled with one
    `select` policy `auth.uid() = id` for `authenticated` and **no** insert/update/delete policy;
    `after insert on auth.users` trigger creates the row idempotently via `security definer` +
    `on conflict (id) do nothing`; `before update` trigger owns `updated_at`) plus `supabase/README.md`.
    Backend: `app/profiles.py` (`UserProfile`, `ProfileRowLike`/`ProfileQueryLike`/`ProfileStore`
    protocols, `SupabaseProfileStore` via the service-role client with a `client_factory` seam,
    `load_user_profile`, `ProfileRowNotFoundError`); `GET /me` in `app/main.py` behind
    `require_authenticated_user`, returning `{user_id, created_at, updated_at}` — 500 (not 404) when a
    verified identity has no row, so profile existence cannot be probed. 11 new tests
    (`tests/test_profiles.py`) asserting migration SQL structure, scoped store query, body-only profile
    fields, unauthenticated 401, own-row-only resolution, and the no-leak 500. Frontend:
    `lib/api-base-url.ts` (single read of `NEXT_PUBLIC_API_URL`; `app/health-api.ts` now re-exports it),
    `lib/auth.ts` gained `getAccessToken` (token handed to one request, never stored/rendered),
    `lib/profile-api.ts` (`fetchMyProfile`, injectable token + `fetch`, typed results, `unauthenticated`
    distinct from `http`), `components/profile-status.tsx` mounted only for a signed-in session, 8 new
    tests; `test` script covers the new file.
  - **Task 3.2 (2026-09-29):** Authentication Model over Supabase Auth — no profiles, no protected
    endpoints, no application data. Frontend: `lib/auth.ts` (only module touching Supabase Auth;
    `signUpWithEmail`/`signInWithEmail`/`signOut`/`getCurrentSession`, typed never-throwing results, fixed
    user-safe messages, pending-confirmation is not sign-in; session from Supabase storage, no token
    handling); `/signup` + `/login` via shared `components/auth-form.tsx` (CSS module + globals base
    controls); `components/auth-status.tsx` on the home page (state display + sign-out); 16 boundary tests
    with a faked `AuthClientLike` seam, no live service. Backend: `app/auth.py` (`AuthenticatedUser`,
    `require_authenticated_user` dependency (unused by endpoints yet), `SupabaseAccessTokenVerifier`
    distinguishing rejected tokens (401) from unavailable Supabase (503), strict `Authorization: Bearer`
    parsing; provider text never returned or logged, exception type only). 25 boundary tests incl. body
    `user_id` distrust, token-absence in responses and logs, `/health` stays public, no-config startup.
    Backend: `supabase==2.31.0` added (`supabase>=2,<3`, uv.lock updated); `app/supabase_client.py`
    (`get_supabase_client` / `is_supabase_configured` / `SupabaseNotConfiguredError`, service-role key,
    construction-only, fresh client per call); `AGENTSCHAT_API_SUPABASE_URL` +
    `AGENTSCHAT_API_SUPABASE_SERVICE_ROLE_KEY` settings (both-or-neither validator, `supabase_configured`
    property); lifespan verifies construction and logs only configured/unconfigured state (never URL/key);
    `apps/api/.env.example` added (placeholders only). Frontend: `@supabase/supabase-js==2.117.2` exact pin
    (npm, 8 packages, 0 vulns); `lib/supabase-client.ts` (shared browser client, public URL + anon key only,
    `null` when unconfigured, no logging); `lib/supabase-client.test.ts` + `supabase-client-unconfigured.test.ts`;
    `test` script covers all three files; `apps/web/.env.example` gained the two public vars. Tests:
    `tests/test_supabase.py` (7 tests: defaults, pair loading, half-pair rejection, clear missing error,
    construction, unconfigured lifespan + /health). No page uses the browser client yet.
  - **Task 5.2 (2026-10-03):** conversation creation. Backend: `POST /conversations`
    (`response_model=Conversation`, `201`) with `CreateConversationRequest` (`title` optional, max 200 —
    `MAX_CONVERSATION_TITLE_LENGTH`), `normalize_conversation_title` (trimmed, blank → `None`), the
    `get_conversation_store` dependency and a thin handler that delegates to `ConversationStore.create`
    with the verified `user.user_id`. Ownership is never read from the body — `user_id` is absent from the
    request model, so a forged field is dropped by validation. `app/conversations.py` gained the
    `ConversationStore` protocol, `SupabaseConversationStore` (single-row insert of exactly
    `(user_id, title)` through the service-role client, columns read back, `ConversationCreateError`) and
    narrow `Protocol` seams mirroring the client chain. `ConversationCreateError`,
    `PostgrestAPIError`/`SupabaseException`/`SupabaseNotConfiguredError`/`HTTPError` all map to a fixed
    `503 {"detail": "The conversation could not be created."}`; invalid auth stays `401` and invalid input
    `422`. CORS now allows `POST`. 11 new tests in `tests/test_conversation_creation.py` (401 paths, title
    validation and normalization, ownership from the verified identity for two different users, forged
    body `user_id`, store failure, and the insert payload/columns); the Task 5.1 route-surface test now
    asserts `/conversations` exposes exactly `POST`. Frontend: `lib/conversations-api.ts`
    (`createConversation`) posts `{title?}` with the session's bearer token (never a user id), never
    throws, and returns a typed result (`unauthenticated`/`invalid-input`/`network`/`http`/
    `invalid-response`/`unexpected`) with fixed messages; `lib/conversations-api.test.ts` (7 tests) and the
    `test` script updated. No product UI uses it yet.
- **Open questions / pending user input:**
  - The root `package.json` npm workspace glob (`apps/*`) still matches `apps/web`. Task 1.1 decided the app is
    an independent package (`npm install --workspaces=false`); narrowing the glob remains an explicitly scoped
    Hermes change and is not planned inside any AgentsChat task so far.
  - Should `pyproject.toml`'s `readme = "README.md"` be repointed to `docs/hermes-runtime.md` (moved
    Hermes README), and should `apps/desktop/README.md`'s `../../README.md` link follow it?
- **Next steps:**
  - Start the next task only on explicit instruction; read the root `AGENTS.md`, `apps/api/README.md`, and
    `apps/web/README.md` first.
  - `memory-bank/` notes are behind: Tasks 3.3, 4.1, 4.2 and 5.1 are recorded in git history and the app
    READMEs but not in the "What was done" list here.
  - On code changes: `scripts/run_tests.sh` for Hermes source; keep prompt-caching and profile-scope
    invariants.
- **Key files for orientation:** `AGENTS.md` → `README.md` → `docs/hermes-runtime.md` → `memory-bank/*`;
  `SOUL.md` (tone); `pyproject.toml` (pins/env); `package.json` (npm workspaces).
