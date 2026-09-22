# Tech Context — Hermes Agent checkout

## Stack
- Python `>=3.11,<3.14` (cap load-bearing: Rust transitives lack cp314 wheels). Exact `==` pins in `pyproject.toml` (post Mini Shai-Hulud 2026-05-12); `uv lock` after changes; upper bounds on all deps.
- Core deps: `openai`, `httpx`, `rich`, `pyyaml`/`ruamel.yaml`, `jinja2`, `firecrawl-anydoc` (doc extract for `read_file`), `pydantic 2.13.4`, `prompt_toolkit`, `croniter`, Snowball stemming for tool search.
- Provider extras lazy-installed via `tools/lazy_deps.py`. TS sides: desktop/TUI/website (nanostores, thin route roots, colocated actions).
- Entry points: `run_agent.py` (AIAgent), `cli.py`, `model_tools.py`, `toolsets.py`, `hermes_state.py`, `batch_runner.py`, `mcp_serve.py`.

## Layout (filesystem canonical)
`agent/` turn phases + providers/memory/compression/prompt | `hermes_cli/` subcommands, setup/config/plugins/skins/updater + `web_routers/` | `tools/` + `tools/environments/` (7 terminal backends) | `gateway/` + `platforms/` + `builtin_hooks/` | `plugins/` (memory, context_engine, model-providers, kanban, image_gen...) | `skills/` + `optional-skills/` | `cron/` | `ui-tui/` + `tui_gateway/` | `apps/desktop/` + `apps/shared` | `acp_adapter/` | `web/` | `evals/` | `scripts/` (`run_tests.sh`, `run_tests_parallel.py`, compat/profile-scope checks, CI classifiers) | `website/` Docusaurus | `tests/` (~39k tests / ~3.7k files).

## State & config
- User state: `~/.hermes/config.yaml`, `~/.hermes/.env` (secrets only), `~/.hermes/logs/` (`agent.log`, `errors.log`, `gateway.log`); profile-aware via `get_hermes_home()` / `display_hermes_home()` (`hermes_constants.py`). Profiles root `~/.hermes/profiles`.
- Browse logs: `hermes logs [--follow] [--level] [--session]`. SessionDB facade `hermes_state.py`.

## Dev commands
- Env: `source .venv/bin/activate` (or `venv/`, or `$HOME/.hermes/hermes-agent/venv`); `scripts/run_tests.sh` probes in that order.
- **Always `scripts/run_tests.sh`, never bare pytest** (env isolation: creds unset, `TZ=UTC`, temp `HERMES_HOME`, per-file subprocess, no xdist). Examples:
  `scripts/run_tests.sh` | `scripts/run_tests.sh tests/gateway/` | `scripts/run_tests.sh tests/agent/test_foo.py -k test_x`
- Flakes: file retried once (`--file-retries`); signal-killed/timeout never retried; pass-on-retry printed `FLAKY`.
- Lint gates: ruff `PLW1514` (explicit encoding) + `ASYNC210/220/221/251` (no blocking in `async def`); per-file baseline for legacy sites.
- Compat check: `scripts/check_compat_pointers.py`; profile-scope advisory: `scripts/check_profile_scope_patterns.py`.

## Test conventions
- Placement mirrors source: `tests/<topdir>/` (only root-module tests directly in `tests/`); no issue numbers in filenames (cite in docstring).
- No `~/.hermes` writes (autouse `_isolate_hermes_home`); profile tests mock `Path.home()` + set `HERMES_HOME`.
- Behavior contracts over snapshots (no model-list/version/count asserts); never read source text in tests (extract pure/DI-testable fn instead).
- OS-specific: `@pytest.mark.linux_only/macos_only/windows_only` on real host; never patch `sys.platform`; no bare `skipif` (use marker so CI lanes discover).
- E2E with real imports + temp `HERMES_HOME` (two homes A→B→A for profile scope); resolution/config/security/file-net paths must exercise real chain.
- CI lanes: `scripts/ci/classify_changes.py`; Python tests must not assert on `package.json`/TS sources (those belong in vitest).
