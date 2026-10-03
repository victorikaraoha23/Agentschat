# Product Context — AgentsChat

## Why it exists
A user should not have to assemble a runtime, model providers, tool configuration, sandboxes, credentials,
and hosting to get real work out of an AI agent. AgentsChat hosts that: sign in, ask in plain language, get
the result. The user never sees providers, models, queues, workers, or sandboxes — but progress and errors
stay honest, because the machinery is hidden, never the truth about the state of the work.

## Users & surfaces
- **Web app (`apps/web`):** public landing, `/signup` + `/login`, authenticated shell at `/app`, and the
  conversation workspace at `/app/conversations/{conversation_id}` (header, message area, composer).
- **API (`apps/api`):** `GET /health`, `GET /me`, and the conversation endpoints (create, list, read,
  rename, delete) — all scoped to the verified caller.
- **Not built yet:** messaging, agent execution, streaming, files/tools, agent selection, sharing,
  conversation lists in the UI.

## Key experiences delivered so far
- Email/password auth over Supabase with one session boundary reused by every private page.
- Conversations a signed-in user owns, enforced in the API *and* by database RLS, with existence never
  leaking (a foreign conversation answers exactly like a missing one).
- A conversation page that loads a conversation honestly, including real loading, not-found, and
  recoverable error states.

## Product constraints (from root `AGENTS.md`)
- Separate concerns: Next.js renders, FastAPI decides, Supabase stores and enforces, Hermes executes.
- Complexity is introduced only with a stated requirement; no speculative infrastructure or features.
- Hide mechanics, never failure; never report success for an outcome that is unknown.
- AgentsChat must not duplicate Hermes runtime behavior, and Hermes must not bypass product controls.
- One task at a time: implement what was asked, then stop.

# Product Context — Hermes Agent

## Why it exists
Self-improving personal agent: creates skills from experience, improves them in use, nudges itself to persist knowledge, searches past conversations (FTS5 + summarization), models the user (Honcho dialectic). Runs on $5 VPS / GPU cluster / serverless (Modal, Daytona hibernate when idle), driven from Telegram etc. while work happens on cloud VM.

## Users & surfaces
- **CLI:** `hermes` REPL (`cli.py` + `hermes_cli/` mixins), slash commands, `-q` single query.
- **Gateway:** single process serving Telegram, Discord, Slack, WhatsApp, Signal, etc. (`gateway/`).
- **TUI:** Ink React UI (`ui-tui/`) + Python JSON-RPC backend (`tui_gateway/`).
- **Desktop:** Electron (`apps/desktop/`) + dashboard SPA (`web/` + `hermes_cli/web_routers/`).
- **ACP:** adapter for VS Code / Zed / JetBrains (`acp_adapter/`).

## Key experiences
- Real terminal (7 backends: local, docker, ssh, singularity, modal, daytona, vercel sandbox) + browser tool.
- Memory + skills closed learning loop; autonomous skill creation; `agentskills.io` compat.
- Cron scheduler with natural-language jobs, delivery to any platform.
- Delegation: isolated subagents, parallel batch, background units.
- Batch trajectory generation / evals (`batch_runner.py`, `evals/`).
- Any model: Nous Portal, OpenRouter, OpenAI, custom endpoints; `hermes model` switching, no lock-in.

## Product constraints (from AGENTS.md)
- **Prompt caching sacred:** system prompt byte-stable per conversation; only exception is compression. Slash commands mutating prompt state default deferred (next session) + opt-in `--now`.
- **Narrow waist core:** new capability prefers: extend code → CLI+skill → service-gated tool (`check_fn`) → plugin → MCP catalog → new core tool (last resort).
- Expansive at edges (adapters, providers, desktop/TUI), conservative at core tool schema.
