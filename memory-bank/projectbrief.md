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
