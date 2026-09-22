# AgentsChat

A hosted, beginner-friendly AI-agent workspace. A user signs in, describes what they need in plain
language, and the hosted system does the work and returns the result — without the user assembling a
runtime, model providers, tool configuration, sandboxes, credentials, or hosting.

AgentsChat is the **product layer**. The agent runtime is **Hermes**, which AgentsChat uses as an
execution dependency and which is not itself user-visible.

## Current status

**Foundational development stage: the web application skeleton exists; no product functionality does yet.**

The repository contains the engineering constitution, the agent-runtime source that AgentsChat depends on,
and the foundation of the web application (`apps/web`, a single static page). There is **no** API server,
database schema, authentication, chat interface, agent execution, or deployment configuration yet. Nothing
described below as planned is implemented.

## Planned architecture

```
Next.js  (web application)
    |
    v
FastAPI  (backend / API)
    |
    v
Supabase  (authentication + persistent application data)

          +

Hermes execution layer  (agent runtime, separate execution environment)
```

| Layer | Responsibility |
|---|---|
| Next.js | Web application: UI, presentation, client interaction, frontend state and routing |
| FastAPI | Backend/API: endpoints, business logic, validation, authorization, orchestration of product operations |
| Supabase | Authentication infrastructure and persistent application data, including ownership enforcement (Row Level Security) |
| Hermes | Agent runtime: agent execution, runtime tool behavior, agent-level capabilities. Runs out of the API request path, in its own execution environment |

**Hermes is the runtime, not the product.** AgentsChat owns accounts, tenancy, the chat experience,
product data and ownership, authorization, usage limits, and the orchestration of product operations.
Hermes owns agent execution and runtime behavior. The two must not duplicate each other's
responsibilities; the boundary is defined in `AGENTS.md` (§2, §3, §11).

## Development principle

The system is built **atomically**. Each task implements only what it requires, and infrastructure is
introduced only when a concrete, stated requirement justifies it. That is why this repository contains no
queue, cache, broker, container orchestration, or additional database: none is needed yet. `AGENTS.md` §4
lists what must not be added without a documented requirement, and §5 requires every task to stay within
its requested scope.

Engineering standards, security requirements, testing expectations, and the Definition of Done live in
**[`AGENTS.md`](./AGENTS.md)** — read it before making changes.

## Repository layout

AgentsChat application code:

- `apps/web/` — the Next.js web application. Its foundation exists (App Router, TypeScript strict mode,
  one static page); see [`apps/web/README.md`](./apps/web/README.md) for commands.
- `apps/api/` — the FastAPI backend/API. **Not created yet.**

Each application is added by the task that builds it, together with its own tooling (Node/TypeScript for
the web application, Python for the API). **No monorepo framework is used**, and the Python backend is not
placed inside a JavaScript package workspace: the two applications are independent projects that live in
one repository.

Existing content:

- `agent/`, `gateway/`, `hermes_cli/`, `tools/`, `skills/`, `plugins/`, `cron/`, `web/`, `apps/desktop/`,
  `acp_adapter/`, `evals/`, `tests/`, … — the **Hermes runtime source**. It is an execution dependency of
  AgentsChat, not part of the product application. Its README is preserved at
  [`docs/hermes-runtime.md`](./docs/hermes-runtime.md), and each area has its own `AGENTS.md`.
- `docs/` — AgentsChat project documentation.
- `memory-bank/` — short orientation notes maintained across AI-assisted development sessions.

Notes for the tasks that create `apps/*`:

- The root `package.json` declares Hermes npm workspaces with an **`apps/*` glob**, which also matches
  `apps/web`. `apps/web` is an **independent** npm package: install with `npm install --workspaces=false`
  from inside it, so the Hermes monorepo's JavaScript dependencies are never pulled into this app. The
  Hermes-side glob was deliberately left untouched — narrowing it is an explicitly scoped Hermes change,
  not a side effect of an AgentsChat task.
- The root `.gitignore` is upstream Hermes's and contains broad patterns (`data/`, `examples/`, `logs/`,
  `images/`) that also match paths inside future application directories. Verify that new application files
  are not silently ignored.
- The Hermes runtime requires Python `>=3.11,<3.14` (`pyproject.toml`).

## Roadmap

**Current stage — Stage 1: application foundation.** Stage 0 (governance, documentation, repository
hygiene) is complete, and the Next.js web application exists as a buildable, renderable skeleton. No
product functionality exists yet.

High-level upcoming stages:

1. Application skeletons: the Next.js web application and the FastAPI backend, with the API boundary
   between them defined.
2. Authentication and persistent user data on Supabase, with ownership enforced in the API and the
   database.
3. Agent execution wired through the Hermes adapter boundary, with explicit run states, limits, and
   cancellation.
4. The chat experience over real runs, with honest progress reporting and review of results.
5. Later — files and tools, memory, and multi-agent workflows, each only when the product requires it.

Detailed sequencing and acceptance criteria belong to the individual tasks; this list intentionally does
not restate the build plan.

## Environment configuration

No environment variables are required at this stage, so **no AgentsChat `.env.example` exists yet** — the
web application foundation needs no configuration. One will be added by the first task that actually needs
configuration (see `AGENTS.md` §16).

The root `.env.example` is **upstream Hermes runtime** configuration and is unrelated to AgentsChat: it
contains non-secret runtime defaults (timeouts, debug flags) plus commented-out placeholder credentials,
and nothing in it needs to be set for AgentsChat work today.
