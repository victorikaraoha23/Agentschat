# Project Brief — AgentsChat (agentschat checkout)

## AgentsChat (the product being built here)
- **What:** a hosted, beginner-friendly AI-agent workspace: sign in, describe the work in plain language,
  the hosted system does it and returns the result.
- **Layers:** `apps/web` (Next.js) → `apps/api` (FastAPI) → `supabase/` (auth + data, RLS-enforced).
  Hermes (this checkout's runtime source) is an execution dependency the product has not yet wired up.
- **Constitution:** the root `AGENTS.md` governs all AgentsChat code; Hermes areas keep their own guides
  (Appendix A). The runtime must never absorb product concerns (accounts, tenancy, authorization).
- **Stage (2026-10-03):** auth + profiles + full conversation CRUD (API, RLS, typed browser client) and
  the conversation page shell are done. Message persistence, agent execution, and the Hermes adapter do
  not exist yet. Work is atomic and sequential: one task per session, never more.
- **Current state:** see `memory-bank/activeContext.md`; history in `memory-bank/progress.md`.

# Project Brief — Hermes Agent (agentschat checkout)

- **What:** Personal self-improving AI agent (Nous Research). Same agent core across CLI, messaging gateway (~20 platforms), TUI, Electron desktop app.
- **Key traits:** learning loop (memory + skills + curator), subagent delegation, cron jobs, real terminal + browser, plugins/skills as extension mechanism (not core growth).
- **Version:** 0.21.4 (`pyproject.toml`). Python `>=3.11,<3.14`. MIT license.
- **Branch:** `update` (remote `https://github.com/victorikaraoha23/Agentschat.git`).
- **Working dir:** `c:\Users\hp\Documents\vibe code\agentschat` (Windows, VS Code, PowerShell).

## Goals for this memory bank
- Preserve durable project orientation across sessions: what Hermes is, how it's structured, invariants, workflows.
- Record active work, decisions, and next steps so future sessions resume without re-discovery.
- Stay aligned with `AGENTS.md` governance (root + area files).

## Scope / non-goals
- Memory bank is documentation/orientation only; it does not change runtime behavior.
- Source of truth remains code + `AGENTS.md` + `website/docs/`; memory bank summarizes and points.

## Success criteria
- `memory-bank/` exists with: projectbrief, productContext, systemPatterns, techContext, activeContext, progress.
- Each file is accurate to current checkout and references area `AGENTS.md` files for detail.
