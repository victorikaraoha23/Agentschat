# Active Context

- **Date:** 2026-09-21. Checkout branch `update`.
- **Current task:** Initialize memory bank (this change). No product code touched.
- **What was done:**
  - Inspected repo root (`Get-ChildItem`), `README.md`, `AGENTS.md` (root), `SOUL.md`, `pyproject.toml`, area guides (`agent/`, `tools/`, `gateway/`, `hermes_cli/`).
  - Attempted codebase-wide regex search for existing `memory-bank` — timed out (large tree); proceeded with standard Cline structure instead of assuming absence of conflicts.
  - Created `memory-bank/` with six files (this bank).
- **Open questions / pending user input:**
  - None blocking. Optional: preferred memory-bank depth/ritual (e.g., update `activeContext`/`progress` each session? track per-task decision log?).
  - Whether to add bank maintenance to a skill or contributing note (not done — kept footprint minimal per narrow-waist rule).
- **Next steps:**
  - User states next task; update `activeContext.md` + `progress.md` as work proceeds.
  - On code changes: read relevant area `AGENTS.md` first (routing table in `projectbrief`/root guide), use `scripts/run_tests.sh`, keep prompt-caching + profile-scope invariants.
- **Key files for orientation:** `AGENTS.md` (root) → area files; `SOUL.md` (tone); `README.md` (product); `pyproject.toml` (pins/env).
