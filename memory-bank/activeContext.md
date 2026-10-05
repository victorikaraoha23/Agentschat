# Active Context

- **Date:** 2026-10-05 (Task 8.3: streaming execution and review fixes).
- **Current task:** Task 8.3 (streaming and frontend execution) is **implemented**. The conversation
  page calls `POST .../execute/stream`, displays streamed output and confirms the persisted reply.
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
  - **Task 5.3 (2026-10-03):** conversation retrieval. Backend: `GET /conversations` and
    `GET /conversations/{conversation_id}`, both behind `require_authenticated_user` and both scoped in
    the query itself to the verified `user_id` (`eq("user_id", ...)`) — the service-role client bypasses
    RLS, so the store filter is the ownership boundary. The list answers `{"items": [...]}` ordered by
    `updated_at` descending with `id` descending as a deterministic tiebreak; the single read validates
    the path id as a UUID (`422`) and uses `maybe_single()`, so a missing conversation and someone
    else's conversation both return `404 {"detail": "Conversation not found."}` — indistinguishable by
    design. Store failures map to fixed `503` details (`The conversations could not be read.` /
    `The conversation could not be read.`); `app/conversations.py` gained the read Protocols,
    `list_for_user` and `get_for_user`, plus `CONVERSATION_COLUMNS` shared by every statement.
    Frontend: `lib/conversations-api.ts` gained `listConversations` and `getConversation` with the same
    never-throwing typed-result pattern (`not-found` added to the reason union, per-operation fixed
    messages, 5 s deadline, `GET` carries only the bearer token — never a user id). Tests: new
    `tests/test_conversation_retrieval.py` (23 tests: endpoints + store-level ownership, the
    indistinguishable 404s, deterministic ordering, empty list, failure mapping); the route-surface test
    now asserts `[GET, POST]` on `/conversations` and `[GET]` on the detail route with no
    `PATCH/PUT/DELETE`; `lib/conversations-api.test.ts` grew to 23 tests (16 new for list/read).
    Docs updated (root `README.md`, both app READMEs). No UI, mutation, message, or Hermes work.
  - **Task 5.4 (2026-10-03):** conversation deletion & renaming — the initial conversation CRUD domain
    is complete. Backend: `PATCH /conversations/{conversation_id}` (body `{"title": ...}` only; the same
    title rules as creation — trimmed, blank/`null` clears to `NULL`, 200-char cap with `422`, forged
    `user_id` dropped) returns the updated conversation with `200`; `DELETE /conversations/{conversation_id}`
    answers `204 No Content`. Both require authentication and scope their statement in the query to the
    verified `user_id` together with the id, so a foreign id matches nothing and answers the same
    `404 {"detail": "Conversation not found."}` as a missing one — existence never leaks. `updated_at`
    is refreshed by the migration's before-update trigger, never written by the application. Store
    failures map to fixed `503` details (`The conversation could not be updated.` /
    `The conversation could not be deleted.`); `app/conversations.py` gained `rename_for_user`,
    `delete_for_user`, and the write Protocols; CORS `allow_methods` gained `PATCH`/`DELETE`. Frontend:
    `lib/conversations-api.ts` gained `renameConversation` (returns the conversation) and
    `deleteConversation` (`ConversationDeleteResult`: bare `{ ok: true }` on the 204), same
    never-throwing typed results with fixed messages. Tests: new `tests/test_conversation_management.py`
    (30 tests: auth, ownership isolation, validation, persistence, store-level owner-scoped
    statements, safe 503/500 failures, and the full create → retrieve → rename → list → delete
    lifecycle); the route-surface test now asserts `[DELETE, GET, PATCH]` on the detail route, no
    `PUT`, and no modification verb on any other path; a CORS preflight test covers `PATCH`/`DELETE`;
    `lib/conversations-api.test.ts` grew to 37 tests (14 new). Docs updated (root `README.md`, both app
    READMEs). No messages, chat UI, agents, Hermes, streaming, or infrastructure.
  - **Task 6.1 (2026-10-03):** conversation page — Phase 6 begins, and the first chat UI. The route
    `/app/conversations/[conversationId]` lives in the authenticated `(app)` group; its `page.tsx` is a
    **server** component that awaits `params` (Next 16 `PageProps<"/app/conversations/[conversationId]">`,
    typed-route verified in `.next/types/routes.d.ts`) and passes **only** `conversationId` to the client
    `conversation-page.tsx`. No second authentication system: access is the existing session from
    `lib/auth.ts` mapped through `toShellAccess`, so no private content renders before a session is
    granted, and nothing about ownership comes from the URL or client state — `getConversation` carries
    the bearer token and the API decides. Two new **pure** lib modules carry the logic, mirroring
    `lib/shell-access.ts`: `lib/conversation-view.ts` (`toConversationPageView`, `conversationTitle`,
    `UNTITLED_CONVERSATION`) maps session + typed result to exactly one view — `loading` | `denied`
    (session denials plus `rejected` for a refused token) | `not-found` | `error` (recoverable, fixed
    message, **Try again**) | `ready`; `not-found` and `invalid-input` collapse to one not-found view, so
    a foreign conversation, a missing one, and a malformed id stay indistinguishable; and
    `lib/conversation-composer.ts` holds the composer rules — send enabled only for a non-whitespace
    draft, submit shows `COMPOSER_NOTICE_MESSAGE` ("messages are not sent yet") in a `role="status"`
    region and **keeps** the draft, because nothing was delivered (no fake request, no fake reply).
    Components are colocated with the route (`conversation-header.tsx`, `conversation-empty-state.tsx`,
    `chat-composer.tsx`) plus page-scoped `conversation.module.css`; tokens/`.surface`/focus-visible come
    from `app/globals.css`, layout is one column that stacks the Send button under the field below
    `30rem` — no device detection, no skeleton infrastructure, no state library. The loaded result is
    tagged with its id and attempt, so navigating between conversations or retrying never shows the
    previous answer. Tests: 25 new (`lib/conversation-view.test.ts` 17, `lib/conversation-composer.test.ts`
    8) → `npm test` **105 passed**; `next typegen && tsc --noEmit` exit 0; `eslint` exit 0; `next build`
    exit 0 with `/app/conversations/[conversationId]` as a dynamic route; `uv run pytest -q` unchanged at
    174 passed. Docs updated (root `README.md`, `apps/web/README.md`). Deliberately **not** implemented:
    message persistence/API/table, assistant responses, streaming, agents, Hermes, rename/delete UI,
    conversation sidebar, search, sorting, folders, skeletons, caching, or any dependency.
  - **Backfilled 2026-10-03** (these tasks were completed earlier but were missing from this list):
    - **Task 3.1 (2026-09-22, commit `c614563c3c`)** Supabase **connectivity boundary only** — backend
      `AGENTSCHAT_API_SUPABASE_URL` + `..._SERVICE_ROLE_KEY` settings that accept both-or-neither (a
      validator rejects half-pairs, naming the fields) and verify SDK construction at startup without a
      network call; frontend `lib/supabase-client.ts` reads exactly the two public `NEXT_PUBLIC_*` values
      and returns `null` when either is absent. No auth, tables, queries, or repositories.
    - **Task 4.1 (2026-10-03, commit `34b57e8d2c`)** authenticated application shell at `/app` —
      `components/app-shell.tsx` gates on `lib/shell-access.ts` (`toShellAccess`, `SHELL_NAV`) over the
      existing session, showing loading, then denial or the header, and `components/profile-status.tsx`
      confirms `GET /me`.
    - **Task 4.2 (2026-10-03, commit `bcdb956244`)** minimal design foundation in `app/globals.css` —
      semantic tokens (light/dark), element styles, `.surface` / `.shell-nav` / `.app-shell*`, visible
      `:focus-visible`, and `prefers-reduced-motion` handling. No framework or component library.
    - **Task 5.1 (2026-10-03, commit `bf6ce941c6`)** conversation schema — `supabase/migrations/
      0002_create_conversations.sql`: `conversations` (`id` uuid default `gen_random_uuid()`, `user_id`
      → `public.profiles (id)` on delete cascade, nullable `title`, `created_at`/`updated_at`, an index
      on `user_id`, and a `before update` trigger `handle_conversations_updated_at`) with RLS enabled and
      four owner-scoped policies on `auth.uid() = user_id`; the insert policy's `with check` rejects a
      client-supplied `user_id`, so the policies fail closed.
    - **Task 8.2 (2026-10-05)** assistant response persistence. `supabase/migrations/
      0004_allow_assistant_message_role.sql` drops `messages_role_user_only` and adds
      `messages_role_user_or_assistant check (role in ('user','assistant'))` -- existing rows stay
      valid, no policy or grant changes, and `system`/`tool`/`function`/`agent` stay refused.
      `app/messages.py` gained `create_assistant_for_user`; both public writes now delegate to one
      private `_insert_owned_message`, so an assistant row has no looser path that skips the
      owner-scoped conversation read. `POST .../execute` now answers with `ExecutionResponse`
      (`status`/`content`/`message_id`) and returns `content` read back from the persisted row. A
      reply that cannot be stored answers `503`, never a completion.
    - **Task 8.1 (2026-10-05, commit `90e3ecbdf4`)** `POST /conversations/{conversation_id}/execute` --
      verified identity -> owner-scoped user-message persistence -> `RuntimeRequest` -> `AgentRuntime`
      -> typed result, with one run per request and the four runtime failures mapped to fixed details.
- **Open questions / pending user input:**
  - The root `package.json` npm workspace glob (`apps/*`) still matches `apps/web`. Task 1.1 decided the app is
    an independent package (`npm install --workspaces=false`); narrowing the glob remains an explicitly scoped
    Hermes change and is not planned inside any AgentsChat task so far.
  - Should `pyproject.toml`'s `readme = "README.md"` be repointed to `docs/hermes-runtime.md` (moved
    Hermes README), and should `apps/desktop/README.md`'s `../../README.md` link follow it?
- **Next steps:**
  - Start the next task only on explicit instruction; read the root `AGENTS.md`, `apps/api/README.md`, and
    `apps/web/README.md` first. Task 8.3 streaming and frontend execution are implemented.
  - The user -> agent -> reply loop now includes the frontend: `POST .../execute/stream` confirms
    the user row, streams provisional deltas, then confirms the persisted assistant row. Navigation
    aborts active submissions and releases runtime resources. Message-history retrieval remains
    a later task; the page shows messages from the current visit.
  - Conversation continuity is still absent: the Hermes adapter uses a disposable workspace per run
    (Task 7.2), so `conversation_id` is passed in the contract but no agent session survives between
    turns. Resuming per conversation needs a durable per-run workspace and is its own task.
  - `memory-bank/` was brought up to date on 2026-10-03: the previously missing task entries (3.1, 4.1, 4.2,
    5.1) were backfilled here and in `progress.md`, and the four Hermes-oriented files
    (`projectbrief.md`, `productContext.md`, `systemPatterns.md`, `techContext.md`) now carry an
    AgentsChat section instead of describing the runtime only.
  - On code changes: `scripts/run_tests.sh` for Hermes source; keep prompt-caching and profile-scope
    invariants.
- **Key files for orientation:** `AGENTS.md` → `README.md` → `docs/hermes-runtime.md` → `memory-bank/*`;
  `SOUL.md` (tone); `pyproject.toml` (pins/env); `package.json` (npm workspaces).
