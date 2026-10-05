# AgentsChat

A hosted, beginner-friendly AI-agent workspace. A user signs in, describes what they need in plain
language, and the hosted system does the work and returns the result — without the user assembling a
runtime, model providers, tool configuration, sandboxes, credentials, or hosting.

AgentsChat is the **product layer**. The agent runtime is **Hermes**, which AgentsChat uses as an
execution dependency and which is not itself user-visible.

## Current status

**Development stage: the web application has signup/sign-in/sign-out, the API resolves authenticated users' AgentsChat profiles and lets a signed-in user create, list, read, rename, and delete conversations they own, and a signed-in user can send a message for agent execution through the runtime boundary — which persists the request, runs the agent through the Hermes adapter, and stores the reply. The conversation page at `/app/conversations/{conversation_id}` shows the conversation's messages and can send a message, but it does not yet call the execution endpoint, and no reply is streamed.**

The repository contains the engineering constitution, the agent-runtime source that AgentsChat depends on,
and the foundations of both applications (`apps/web`: signup, sign-in, sign-out, session detection over
Supabase Auth, a one-line profile confirmation, and the conversation page shell; `apps/api`:
`GET /health`, the authentication boundary,
`GET /me`, which returns the signed-in user's profile, and the conversation endpoints —
`POST /conversations`, `GET /conversations`, `GET /conversations/{conversation_id}`,
`PATCH /conversations/{conversation_id}`, and `DELETE /conversations/{conversation_id}` — which create,
read, rename, and delete conversations owned by the signed-in user). The schema exists as versioned Supabase migrations
(`supabase/migrations/`: a `profiles` table and a `conversations` table, each with Row Level Security).
Messaging and agent execution exist on the API side: a signed-in user can post a message, run it
through the agent runtime, and see the request and the reply stored in the conversation. There is
still **no** streaming, no message-history retrieval endpoint, no frontend assistant view, and no
production deployment. Nothing described below as planned is implemented.

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

- `apps/web/` — the Next.js web application: signup, sign-in, sign-out and session detection over
  Supabase Auth (`/signup`, `/login`, account status on the home page), the `GET /me` profile
  confirmation, and the conversation page (`/app/conversations/{conversation_id}`) with its header,
  empty message area and composer; see [`apps/web/README.md`](./apps/web/README.md) for commands.
- `apps/api/` — the FastAPI backend/API: `GET /health`, the authentication boundary
  (`AuthenticatedUser`, `require_authenticated_user`), `GET /me`, which resolves the signed-in user's
  profile from `public.profiles`, and the conversation endpoints — `POST /conversations`,
  `GET /conversations`, `GET /conversations/{conversation_id}`, `PATCH /conversations/{conversation_id}`,
  and `DELETE /conversations/{conversation_id}` — which create, read, rename, and delete conversations
  owned by the verified caller; see [`apps/api/README.md`](./apps/api/README.md) for commands.
- `supabase/` — versioned SQL migrations for the application database (the `profiles` table and the
  `conversations` table, each with Row Level Security policies); see
  [`supabase/README.md`](./supabase/README.md).

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

Notes for the `apps/*` applications:

- The root `package.json` declares Hermes npm workspaces with an **`apps/*` glob**, which also matches
  `apps/web`. `apps/web` is an **independent** npm package: install with `npm install --workspaces=false`
  from inside it, so the Hermes monorepo's JavaScript dependencies are never pulled into this app. The
  Hermes-side glob was deliberately left untouched — narrowing it is an explicitly scoped Hermes change,
  not a side effect of an AgentsChat task.
- The root `.gitignore` is upstream Hermes's and contains broad patterns (`data/`, `examples/`, `logs/`,
  `images/`) that also match paths inside future application directories. Verify that new application files
  are not silently ignored.
- `apps/api` is an independent **uv** project (its own `pyproject.toml`, `.venv`, and `uv.lock`): run
  `uv sync` / `uv run` from inside it, never from the repository root, whose `uv.lock` belongs to Hermes.
- The Hermes runtime requires Python `>=3.11,<3.14` (`pyproject.toml`).

## Roadmap

**Current stage — Stage 1: application foundation.** Governance, the Supabase connectivity boundary, and
the authentication model are complete: the web application creates and uses Supabase Auth sessions, the API
resolves the authenticated identity and their `profiles` row behind `GET /me`, and the schema now ships as
versioned migrations for both `profiles` and `conversations`. Conversation **creation, retrieval,
renaming, and deletion** are in place (`POST /conversations`, `GET /conversations`,
`GET /conversations/{conversation_id}`, `PATCH /conversations/{conversation_id}`, and
`DELETE /conversations/{conversation_id}`, all scoped to the verified caller). Messages are persisted
(`POST /conversations/{conversation_id}/messages`), and a message can be submitted for agent execution
(`POST /conversations/{conversation_id}/execute`), which stores the request, runs it through the runtime
contract and Hermes adapter, and stores the assistant's reply as a second message in the same
conversation. The conversation page renders a conversation's messages and can send a message, but does
not yet call the execution endpoint.

High-level upcoming stages:

1. Message-history retrieval and the frontend chat experience over real runs, with the execution
   endpoint wired to the composer and honest progress reporting.
2. Streaming agent output, with explicit run states, limits, and cancellation.
3. Later — files and tools, memory, and multi-agent workflows, each only when the product requires it.

Detailed sequencing and acceptance criteria belong to the individual tasks; this list intentionally does
not restate the build plan.

## Environment configuration

`apps/web` has two **optional, client-visible** variables: `NEXT_PUBLIC_API_URL`, the base URL of the API as
seen from the browser, and the public Supabase pair (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`),
which also powers Supabase Auth. They default to unset (the Supabase ones) or `http://127.0.0.1:8000`, so
local development needs no setup and authentication simply reports itself unavailable;
`apps/web/.env.example` documents them. Never place a secret in a `NEXT_PUBLIC_*` variable — those values are
compiled into the client bundle (`AGENTS.md` §16).

The API needs no configuration to start: every `AGENTSCHAT_API_*` setting has a safe default, documented in
`apps/api/README.md`.

The root `.env.example` is **upstream Hermes runtime** configuration and is unrelated to AgentsChat: it
contains non-secret runtime defaults (timeouts, debug flags) plus commented-out placeholder credentials,
and nothing in it needs to be set for AgentsChat work today.
