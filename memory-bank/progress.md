# Progress

## Done (2026-09-21)
- Initialized `memory-bank/` with:
  - `projectbrief.md` — mission, scope, success criteria.
  - `productContext.md` — why/users/surfaces/product constraints.
  - `systemPatterns.md` — facade+siblings, agent loop, tools, gateway, CLI, memory/providers, profile scope.
  - `techContext.md` — stack, layout, state/config, dev/test commands, conventions.
  - `activeContext.md` — current task state, next steps.
  - `progress.md` — this file.
- Verified `memory-bank/` directory listing via `Get-ChildItem` (creation observed).

## In progress
- Awaiting user's next task. Task 1.5 is complete; Phase 2 (Task 2.1) is **not** started.

## Done (2026-09-22)
- **Task 0.1 — engineering constitution** (commit `5026704a4e`): root `AGENTS.md` replaced with the
  AgentsChat constitution — mission; Next.js/FastAPI/Supabase/Hermes separation of concerns; dependency
  direction; simplicity (no unjustified Redis/Kafka/Kubernetes/microservices/queues); atomic development;
  type safety; FastAPI API standards with status codes; database + RLS standards; auth vs authz with the
  never-trust-client-values table; security; Hermes adapter boundary; agent safety and resource control;
  error taxonomy; testing; frontend; environment variables; dependencies; code quality; git; documentation;
  no speculative features; 10-point Definition of Done; Appendix A routing to Hermes area guides.
- **Task 0.2 — repository foundation**: root `README.md` now documents AgentsChat (current status, planned
  architecture, atomic development principle, repository layout, roadmap, environment configuration). The
  upstream Hermes runtime README is preserved at `docs/hermes-runtime.md`, with its relative links rebased
  (`../assets/banner.png`, `../LICENSE`, the translated root READMEs) and a provenance note prepended.
  `.gitignore` gained an AgentsChat-only section: Next.js build output and `next-env.d.ts`, Node
  package-manager logs, Python tooling artifacts, editor/OS files, `.env.*.local`, with `!.env.example`
  kept committable.
- Deliberately **not** added in Task 0.2: `apps/web`, `apps/api`, a root `.env.example`, dependencies,
  formatting/linting tooling, CI, Docker, or any service.
- Verification for Task 0.2: `git status` / `git diff` limited to `README.md`, `docs/hermes-runtime.md`,
  `.gitignore` and these bank notes; `pyproject.toml`, `package.json` and `.env.example` untouched; no
  credentials in any changed file (secret-pattern scan clean); README read end to end and makes no claim
  that a feature exists.
- **Task 1.1 — Next.js foundation (`apps/web`)**: scaffolded with `create-next-app` (Next `16.3.5`, React
  `19.2.8`, App Router, TypeScript strict, ESLint, no Tailwind, no `src/`, alias `@/*`). Customized: minimal
  landing page (`app/page.tsx`) naming AgentsChat and stating that only the skeleton exists, layout metadata
  + `app/globals.css` base styles (light/dark), package name `agentschat-web`, `typecheck` script
  (`next typegen && tsc --noEmit`), `public/` kept via `.gitkeep`, `!.env.example` added to the app
  `.gitignore`, boilerplate README replaced with app-local commands.
- Verified for Task 1.1: `npm install --workspaces=false` (347 packages, 0 vulnerabilities; `node_modules`
  and `package-lock.json` stay inside `apps/web`), `npm run lint` exit 0, `npm run typecheck` exit 0,
  `npm run build` exit 0 (static `/` and `/_not-found` prerendered), dev server returned HTTP 200 with
  `<title>AgentsChat</title>` and `<h1>AgentsChat</h1>`, then was stopped. No API, auth, chat, Supabase or
  Hermes integration exists.
- **Task 1.2 — web structure and conventions**: reviewed the Task 1.1 structure and **kept it unchanged** —
  it already provides App Router routes (`app/`), a root layout plus one page, and shared styling
  (`app/globals.css`). No `components/`, `lib/`, `hooks/`, `services/` or `features/` directory was created,
  because nothing belongs in them yet. The deliverable was the convention set, documented in
  `apps/web/README.md`: route/layout organization, server-components-first with `"use client"` only where
  interactivity is needed, styling (global stylesheet plus colocated CSS Modules), where reusable components
  (`apps/web/components/`) and shared utilities (`apps/web/lib/`) go once they exist, the `@/*` import alias,
  TypeScript strict rules, file naming, and formatting (no formatter configured, deferred).
- Verified for Task 1.2: `npm run typecheck` exit 0, `npm run lint` exit 0, `npm run build` exit 0 (static
  `/` and `/_not-found` prerendered), dev server returned HTTP 200 with `<h1>AgentsChat</h1>`, then stopped.
  The diff contained `apps/web/README.md` and these bank notes only — no code, config, or dependency change.

- **Task 1.4 — API configuration (`apps/api/app/config.py`)**: centralized settings via `pydantic-settings`
  (new direct dependency `pydantic-settings>=2,<3`, consistent with the existing bounded-pin style) with
  an `AGENTSCHAT_API_` env prefix and exactly two settings — `app_name` (default `AgentsChat API`) and
  `environment` (default `local`) — behind an `lru_cache` `get_settings()`. Wired the sole concrete
  consumer: `FastAPI(title=settings.app_name)`. `/health` response unchanged. Five behavioral tests in
  `tests/test_config.py` (defaults, overrides, unprefixed-variable isolation, two invalid-input cases).
  No `.env.example`: the API starts with defaults, loads no `.env`, and has no secrets to document; the
  two variables are documented in `apps/api/README.md` instead.
- Verified for Task 1.4: `uv sync` exit 0 (installed pydantic-settings 2.15.0 with python-dotenv 1.2.3
  transitively; root `uv.lock` untouched); `uv run pytest -q` → **6 passed**; live server on defaults →
  `GET /health` **200** `{"status":"healthy"}` and OpenAPI title `AgentsChat API`; live server with
  `AGENTSCHAT_API_APP_NAME` set → title `AgentsChat Override Check` while `/health` stayed byte-identical;
  `Settings(environment="")` raises `ValidationError` naming the field; `apps/api/.env` does not exist;
  both servers stopped and env vars cleared (0 listeners); diff limited to the five API files, the
  updated `apps/api/uv.lock`, and the two memory-bank records.

- **Task 1.5 — web ↔ API connection**: `apps/web/app/health-api.ts` calls `GET /health` with the platform
  `fetch` behind a typed result union (`ok` / `network` / `http` / `invalid-response`) and never throws;
  `app/page.tsx` is the smallest `"use client"` component that renders honest states (frontend running /
  checking / succeeded / failed) in an `aria-live` region. The base URL comes from the single optional
  `NEXT_PUBLIC_API_URL` (default `http://127.0.0.1:8000`), documented by the new `apps/web/.env.example`;
  the default is inlined into the client bundle at build time. CORS became real because the call is
  browser-side: the API allows exactly the two local development origins for `GET` (`DEV_ALLOWED_ORIGINS`,
  no wildcard, no production origin yet). Frontend tests use Node's built-in runner (`npm test` →
  `node --test`) with an injected `fetch` seam — no test framework dependency; the native runner needs
  explicit `.ts` import specifiers, so `tsconfig.json` gained `allowImportingTsExtensions` (legal under the
  existing `noEmit`). Root and app READMEs, the API's CORS section, and the roadmap were updated.
- Verified for Task 1.5: `uv run pytest -q` → **11 passed** (6 existing + 5 new CORS tests);
  `npm test` → **5 passed / 0 failed**; `npm run typecheck` exit 0; `npm run lint` exit 0;
  `npm run build` exit 0 (static `/` and `/_not-found`); live `uvicorn` plus the real `health-api.ts`
  module run by Node → `{"ok":true,"status":"healthy"}` (exit 0) and, pointed at a closed port,
  `{"ok":false,"reason":"network","message":"fetch failed"}` (exit 0, nothing thrown); `curl` with
  `Origin: http://localhost:3000` → `access-control-allow-origin` present, with an unlisted origin →
  header absent; dev server returned **200** with the "Frontend: running" / "checking…" markup and the API
  URL found in a client chunk; both servers stopped and every port released; secret scan clean; new/edited
  files LF per `.gitattributes`.
- Observation (not fixed, deliberately deferred): `npm test` prints `MODULE_TYPELESS_PACKAGE_JSON` because
  `apps/web/package.json` has no `"type": "module"` — a reparse cost in the test run only. The
  `npm warn Unknown project config "min-release-age"` lines originate in the Hermes root npm config and are
  pre-existing.

## Backlog / reminders
- Keep bank in sync when architecture or workflows change (point to `AGENTS.md`/code, don't duplicate).
- Suggested update ritual: after each task, append decisions + verification under a dated heading here and refresh `activeContext.md`.
- Hermes-source tests run through `scripts/run_tests.sh` (never a bare `pytest`) and have not been needed, because no Hermes source has been modified. Web-app changes are validated inside `apps/web` with `npm run lint`, `npm run typecheck`, `npm run build`, and a dev-server render check.
- Pre-existing repository CI items, verified as **not** caused by the AgentsChat web skeleton and out of scope for these tasks (each needs repo-settings or maintainer action in the Hermes-derived CI): `codeql.yml` ("CodeQL Advanced", a stock template added by `16e5a2161b`, whose matrix includes `ruby` although the checkout has no Ruby sources) fails to complete; `review-labels.yml` requires the `ci-reviewed` label whenever a CI-sensitive file changes, which flagged the scaffold-generated `apps/web/eslint.config.mjs` (added, never edited); Socket reports obfuscation heuristics on `eslint-plugin-react` and `damerau-levenshtein`, both transitive devDependencies of `eslint-config-next`.

- **Task 1.3 — FastAPI foundation (`apps/api`)**: created an independent `uv` project (`pyproject.toml`,
  `uv.lock`, `.venv`) with `app/main.py` exposing a typed `GET /health` (`HealthResponse` response model;
  exact body `{"status": "healthy"}`; no secrets, environment details, or infrastructure info) and
  `tests/test_health.py` using FastAPI's `TestClient`. App-local README documents install, run, and test
  commands only. Isolation verified: the Hermes setuptools package-find `include` list excludes `apps/`,
  the Hermes root pytest `testpaths = ["tests"]` does not collect `apps/api`, and the root `uv.lock` is
  untouched. No auth, database, CORS, global handlers, logging, or Hermes integration. Root `README.md`
  status/layout/roadmap/environment sections updated to match reality.
- Verified for Task 1.3: `uv sync` exit 0 (resolved fastapi 0.141.1, uvicorn 0.53.0, pydantic 2.13.5,
  pytest 9.1.1, httpx 0.28.1); import check exit 0 (`/health` route present); `uv run pytest -q` →
  **1 passed**; live `uvicorn` on port 8000 → `GET /health` returned **200** with exactly
  `{"status":"healthy"}` and `content-type: application/json`, port released after stop;
  `npm run typecheck` in `apps/web` exit 0 with zero `git status` changes under `apps/web`; new and edited
  files are LF per `.gitattributes`.

- **Ad-hoc — Vercel readiness for `apps/web`**: proved with a local dry run that plain `npm install` from
  `apps/web` climbs into the Hermes workspace root (`npm prefix` → repository root; the Hermes root
  `postinstall` executed), which would misroute a default Vercel install. Added `apps/web/vercel.json`
  pinning `installCommand` to `npm install --workspaces=false` (the command used since Task 1.1),
  documented the dashboard-side Root Directory requirement in `apps/web/README.md`, and corrected the root
  `README.md` claim about deployment configuration. No CI, Docker, or build-output changes.
- Verified for the Vercel readiness change: the pinned install command re-ran from `apps/web` with the
  root `package-lock.json` hash unchanged and root `node_modules` still absent; `npm run lint`,
  `npm run typecheck`, `npm run build` → exit 0; `vercel.json` parses and is not git-ignored while
  `.vercel/` stays ignored; diff limited to five intended files.

## Decision log
- 2026-09-21: Used standard Cline six-file bank (projectbrief/productContext/systemPatterns/techContext/activeContext/progress) since repo-wide search timed out and no existing bank was visible at root listing. Content grounded in `AGENTS.md` + area guides + `README` + `pyproject`, not invented.
- 2026-09-22: AgentsChat application code will live in `apps/web` (Next.js/TypeScript) and `apps/api`
  (Python/FastAPI) as two independent projects; no monorepo framework, and the Python backend is not placed
  inside a JavaScript workspace. The root `package.json`'s `apps/*` npm workspace glob was deliberately left
  untouched — the task that creates `apps/web` decides whether it joins that workspace.
- 2026-09-22: The upstream Hermes README was **moved** to `docs/hermes-runtime.md` (not deleted) because it
  documents the runtime dependency, and its relative links were rebased so the document stays coherent.
  Known consequences left for an explicitly scoped Hermes task: `pyproject.toml` still declares
  `readme = "README.md"`, so Hermes wheel metadata carries the AgentsChat README, and
  `apps/desktop/README.md` still links `../../README.md`.
- 2026-09-22: No root `.env.example` was added for AgentsChat — no configuration is required yet, and adding
  placeholder config for features that do not exist is prohibited by `AGENTS.md` §16. Formatting/linting and
  type-check tooling for the applications is deferred to the tasks that create them.
- 2026-09-22: `apps/web` is an **independent** npm package (`agentschat-web`), installed with
  `npm install --workspaces=false`, even though the Hermes root `package.json` workspace glob (`apps/*`)
  matches it. The Hermes-side glob was left untouched: narrowing it is an explicitly scoped Hermes change
  (root `AGENTS.md` Appendix A), not a side effect of an AgentsChat task.
- 2026-09-22: Kept the framework-generated `apps/web/AGENTS.md` and `CLAUDE.md` because `next dev` rewrites
  the agent-rules block (deleting it only re-creates an uncommitted change). The root `AGENTS.md` remains
  the governing instruction set; the app file only carries Next.js framework guidance.
- 2026-09-22: Kept the Next 16 scaffold defaults, including the React Compiler
  (`next.config.ts` → `reactCompiler: true` plus `babel-plugin-react-compiler`), rather than hand-tuning a
  framework default in a foundation task. `typecheck` runs `next typegen` first because Next 16 route types
  (`LayoutProps<"/">`) are generated, so `tsc` alone fails on a clean checkout.
- 2026-09-22: Task 1.2 established web structure and conventions **by documentation only**: no directory,
  config, or dependency was added. `apps/web/components/` and `apps/web/lib/` are named as the future homes
  for reusable UI and shared utilities but are deliberately not created (root `AGENTS.md` §5/§18: no
  speculative structure, no empty packages). `tsconfig.json`, `next.config.ts` and `eslint.config.mjs` were
  left exactly as Task 1.1 set them, including the Next 16 defaults.
- 2026-09-22: `apps/api` uses **uv** — the dependency manager already established by the root `uv.lock` —
  as an independent project with its own `pyproject.toml`/`uv.lock`/`.venv`, mirroring the npm decision for
  `apps/web`. No `[build-system]`/package install: pytest uses `pythonpath = ["."]` and uvicorn resolves
  `app.main` from the working directory, so there is no packaging configuration that can drift. Dependency
  floors follow the repository's known-current pins (`fastapi>=0.133`, `uvicorn>=0.41`); uv resolved
  current stable releases (fastapi 0.141.1, uvicorn 0.53.0).
- 2026-09-22: `apps/web/vercel.json` pins only `installCommand`; framework, build command, and output use
  Vercel's Next.js defaults. Root Directory cannot be versioned in the repository (it is a Vercel project
  setting), so it is documented in `apps/web/README.md` instead. No `engines` field was added: Next 16
  requires Node >=20.9.0 and Vercel's default satisfies it, so a pin would guard only against a dashboard
  misconfiguration.
- 2026-09-22: The web → API boundary is **browser-side** `fetch` with `NEXT_PUBLIC_API_URL`, not a
  server-component fetch: the browser must reach the API directly, and client-side failure states stay
  honest. Consequence: CORS is genuinely required, so the API declares an explicit two-origin development
  allowlist (`DEV_ALLOWED_ORIGINS`) — never `*`; production origins arrive with the deployment task.
- 2026-09-22: Frontend tests use Node's built-in runner (`node --test`) with an injected `fetch` seam
  instead of adding Jest/Vitest — no dependency, no network I/O. `tsconfig.json` gained
  `allowImportingTsExtensions` because the native runner requires explicit `.ts` specifiers.
- 2026-09-22: `.env.example` lives in the consuming app (`apps/web/.env.example`), not at the repository
  root, whose `.env.example` is upstream Hermes runtime configuration.
- 2026-09-22: configuration uses `pydantic-settings` in a single module with an `AGENTSCHAT_API_` prefix
  (collision-safe against the Hermes process environment) and `lru_cache` — deliberately no `env_file`, so
  no `.env` is ever read and defaults alone start the app. `python-dotenv` arrives transitively but is
  inert. Absent until a concrete need: CORS, database, auth, provider keys, logging, and any `.env.example`
  template (root `AGENTS.md` §5, §16, §21).
