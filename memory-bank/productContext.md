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
