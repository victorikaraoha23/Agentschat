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
- Awaiting user's next task. Task 1.1 is **not** started.

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

## Backlog / reminders
- Keep bank in sync when architecture or workflows change (point to `AGENTS.md`/code, don't duplicate).
- Suggested update ritual: after each task, append decisions + verification under a dated heading here and refresh `activeContext.md`.
- Validation not yet run: `scripts/run_tests.sh` untouched (no code changed — docs only).

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
