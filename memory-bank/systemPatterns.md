# System Patterns — Hermes Agent

## Facade + siblings (Sep 2026 decomposition)
Every former god file = facade (public entry + imports) + `<stem>_<topic>.py` siblings.
Largest: `hermes_state.py` (21), `gateway/run.py` (15), `tools/mcp_tool.py` (15),
`hermes_cli/kanban.py` (14), `hermes_cli/web_server.py` (13 + 24 routers), `hermes_cli/auth.py` (12),
`tools/browser_tool.py` (11), `cli.py` (12 mixins), `run_agent.py` (`agent/turn_*.py`).

Rules:
- Find code by topic: `grep -rn "def name" <dir>/<stem>_*.py`; facade-first is expensive.
- Siblings may import each other / late-import facade in functions; facade never module-imports a sibling that module-imports it.
- **Patch where production reads** (often `from <facade> import X` inside function) — patch facade attr.
- Compat pointers (`PLUGIN-COMPAT`, `COMPAT_MANIFEST.md`) OFF LIMITS in-tree; CI `scripts/check_compat_pointers.py` enforces.
- No new god files: ~2000-line file / ~300-line fn / CC 30 → split first, own commit.
- No `if/elif` ladder ≥4 on name/kind — dict/table → handler (`_SLASH_DISPATCH`, gateway `_command_handler_table`, `INLINE_TOOL_EXECUTORS`).
- Moving symbol = fix docs same PR (`website/docs`, `skills/`, `AGENTS.md`).

## Agent loop (`run_agent.py` facade + `agent/turn_*.py`)
- `AIAgent` assembled from mixins; `init_agent` (`agent/agent_init.py`); turn = `conversation_loop.py::run_conversation` after session turn lease.
- Synchronous loop, ~500 max iterations, budget + interrupt + one-turn grace.
- OpenAI-format messages; reasoning in `assistant_msg["reasoning"]`.
- Agent-level tools (`todo`, `memory`) intercepted via `INLINE_TOOL_EXECUTORS` table before `handle_function_call()`.
- Invariants: strict role alternation; system prompt byte-stable; mid-conversation injection rides user/tool messages, never system prompt; compression is only sanctioned cache break (prune tool results → boundaries → aux-model summary, in-place, fenced).

## Tools (`tools/` + `toolsets.py` + `model_tools.py`)
- `tools/registry.py` (no deps); each `tools/*.py` `registry.register()` at import; `discover_builtin_tools()`; package tools register from `tools/<pkg>/tool.py` (needs `__init__.py`).
- All handlers return JSON string. `check_fn` TTL-cached keyed by `hermes_home_key()`.
- Tool exposed only if named in toolset (`_HERMES_CORE_TOOLS` default bundle).
- Schema descriptions never name other-toolset tools (added dynamically in `get_tool_definitions()`); paths: `display_hermes_home()` in schema, `get_hermes_home()` at call time; no `offset/limit` on instructional tools.
- Delegation (`delegate_tool.py`): isolated context, single/batch, `background`, roles leaf/orchestrator, depth ≤2, pool slots per unit group; child kernels/processes cleaned at teardown.

## Gateway (`gateway/`)
- Facade `run.py` + `run_*.py` phases + `session*.py` + `slash_commands_*.py` + `authz_mixin.py` + `platforms/<name>.py` over `base.py`. Reads user YAML raw (not `DEFAULT_CONFIG`).
- TWO guards while agent running: base adapter queues in `_pending_messages`; runner intercepts `/stop /new /queue /status /approve /deny`. Control commands must bypass both, dispatched inline.
- Streaming (`draft_stream_is_message`): prefix-stable frames; consumer declares final via `finish(final_text)`; interim sends tagged `_interim_send`; reconcile by edit, never plain send.
- Profile scope: one process serves many profiles; bind via `_profile_runtime_scope` (turn), `@_profile_scoped` (RPC), `_profile_cron_scope` (ticker), `_run_release_in_profile_scope` (eviction). Never `~/.hermes` hardcoded; never `os.environ.copy()` for children (`served_profile_child_env`).

## CLI (`cli.py` + `hermes_cli/`)
- `HermesCLI` + mixins; `COMMAND_REGISTRY` (`commands.py`) single source for dispatch/help/autocomplete; dispatch via `_SLASH_DISPATCH`, no elif.
- Skill slash commands inject as user message (caching).
- Interactive pickers = curses; no `\033[K` in spinner code (space-pad for prompt_toolkit).
- Config: defaults + YAML merge; `.env` secrets only; no new `HERMES_*` env for non-secret config.
- Never infer process identity from argv substrings — canonical matchers + parser-derived flags.

## Memory / providers / plugins
- `agent/memory_provider.py` ABC + `memory_manager.py`; context-engine / image-gen same pattern; providers are plugins (`plugins/model-providers/<name>/`). Cron passes `skip_memory=True`.
- Session-end flush wherever session ends; caller binds profile scope; ground truth = `Path(db_path).parent`, never `os.environ`.
- Secrets via `agent/secret_scope.py::get_secret`; fail-closed only after `set_multiplex_active(True)`; use shared reader, never ad-hoc fallback.
