# AgentsChat Backend

FastAPI service, background worker, and the 7-stage content pipeline.

## Environment

Dependencies are managed with [uv](https://docs.astral.sh/uv/) and installed into a project-local
virtual environment at `backend/.venv` (CPython 3.11, pinned by `.python-version`).

- `.venv` is **gitignored** — never commit it.
- `uv.lock` **is** committed — it pins the full dependency graph for reproducible installs.

Create or refresh the venv:

```bash
uv sync            # create/refresh .venv (the `dev` group is included by default)
uv sync --no-dev   # runtime dependencies only
uv sync --locked   # CI: fail if uv.lock is out of date instead of updating it
```

`uv run` uses `backend/.venv` automatically, so activating is optional. To check which interpreter
is in play:

```powershell
uv run python -c "import sys; print(sys.prefix)"
# C:\...\agentschat\backend\.venv
```

To activate the venv explicitly:

```powershell
.\.venv\Scripts\Activate.ps1        # PowerShell
.\.venv\Scripts\activate.bat        # cmd.exe
```

```bash
source .venv/bin/activate           # macOS / Linux
source .venv/Scripts/activate       # Git Bash on Windows
```

## Commands

Run all of these from `backend/`:

| Command | Purpose |
|---|---|
| `uv run pytest` | test suite (coverage is on via `addopts = "--cov=src"`) |
| `uv run ruff check .` | lint |
| `uv run mypy src` | strict type check |
| `uv run uvicorn src.main:app --reload` | run the API on http://127.0.0.1:8000 |

`GET /health` → `{"status": "ok", "service": "agentschat-api"}`.

## Layout

`src/` is a plain package on `sys.path` from the project root — `pyproject.toml` deliberately
declares **no** `[build-system]`, so nothing is installed into the venv. Invoke `uv run` from
`backend/` so `src.*` imports resolve.


