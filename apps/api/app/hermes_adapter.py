"""Hermes adapter behind the agent runtime contract (Task 7.2).

Boundary owned here::

    API/domain  ->  app/runtime.py (contract)  ->  this module  ->  Hermes

This module is the *only* place that knows how to talk to Hermes, and even it
never imports Hermes: Hermes is reached through its documented, machine-readable
CLI surface, in a child process, so the two runtimes stay separate (root
``AGENTS.md`` §2, §11). Nothing above the boundary may import this module's
internals or learn a Hermes config key, flag, response shape, or file format.

What the child receives and what it is asked for is deliberately narrow:

- the user's text is written to a file inside a fresh per-run workspace and
  handed over with ``--query-file``, so it is never a command-line argument
  (no quoting, no shell interpretation, no argument injection);
- the child gets a fresh empty working directory instead of this application's
  own directory, and an environment with every ``AGENTSCHAT_*`` variable
  removed, so the run never sees the service-role key or this application's
  configuration;
- ``--format stream-json`` returns newline-delimited JSON ending in one
  ``result`` record, which is the only thing that is parsed.

Everything else — accounts, tenancy, quotas, retries, streaming, and the chat
interface that will eventually call ``execute`` — belongs to the application
and is deliberately absent here (root ``AGENTS.md`` §5, §12, §21).
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

from app.logging_config import logger
from app.runtime import (
    RUNTIME_FAILED_MESSAGE,
    RUNTIME_TIMED_OUT_MESSAGE,
    RUNTIME_UNAVAILABLE_MESSAGE,
    RuntimeFailureReason,
    RuntimeRequest,
    RuntimeResult,
)

#: Environment variables of this application that are never passed to Hermes.
#: The child needs the host environment to run, but never AgentsChat's own
#: configuration or credentials (root ``AGENTS.md`` §11, §16).
_AGENTSCHAT_ENV_PREFIX: Final[str] = "AGENTSCHAT_"

#: Name of the query file inside the run's private workspace.
_QUERY_FILENAME: Final[str] = "query.txt"

#: Period between the polite stop and the forced kill of a run that exceeded its
#: time limit (root ``AGENTS.md`` §12: exceeding the limit must release resources).
_KILL_GRACE_SECONDS: Final[float] = 5.0

#: Longest Hermes-reported error kept in a server-side log record: enough to
#: identify the failure, short enough that a large provider payload cannot be
#: copied wholesale into the logs.
_LOGGED_ERROR_LIMIT: Final[int] = 300

#: Longest stderr tail kept in a server-side log record when Hermes produced no
#: usable result at all. Server-side only, never returned to a caller.
_LOGGED_STDERR_LIMIT: Final[int] = 500

#: Fixed, safe summaries are owned by the runtime contract (``app.runtime``)
#: rather than redefined here: callers are told what happened to their work in
#: application terms; the runtime's own error text never leaves this module
#: (root ``AGENTS.md`` §13).


class _HermesResultRecord(BaseModel):
    """The terminal ``result`` record of ``--format stream-json``.

    Hermes's record is an external payload, so it is validated into this model
    rather than read with ad-hoc key access (root ``AGENTS.md`` §6). Tokens,
    duration, and session identifiers are real fields of that record but carry
    no product meaning yet, so they are ignored rather than stored.
    """

    model_config = ConfigDict(extra="ignore")

    type: Literal["result"]
    exit_code: int = 0
    text: str = ""
    error: str | None = None


def _child_environment() -> dict[str, str]:
    """Build the environment handed to Hermes: the host's, minus our own keys.

    Hermes needs the host environment to find its own interpreter, PATH, and
    provider credentials. It must never receive AgentsChat's settings, above
    all the Supabase service-role key (root ``AGENTS.md`` §11).
    """
    return {
        name: value
        for name, value in os.environ.items()
        if not name.upper().startswith(_AGENTSCHAT_ENV_PREFIX)
    }


def _last_result_record(stdout: bytes) -> _HermesResultRecord | None:
    """Return the last ``result`` record of a JSONL stream, or None.

    The stream carries ``system``/``text``/``tool_*`` records before it; only
    the terminal one decides the outcome. Lines that are not valid JSON are not
    a result record and are skipped rather than treated as a crash: the
    subprocess boundary is exactly where an external payload gets checked
    (root ``AGENTS.md`` §6).
    """
    result: _HermesResultRecord | None = None
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            candidate = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(candidate, dict) or candidate.get("type") != "result":
            continue
        try:
            result = _HermesResultRecord.model_validate(candidate)
        except ValueError:
            continue
    return result


def _failure(reason: RuntimeFailureReason, message: str) -> RuntimeResult:
    """Build a failed result in the contract's shape."""
    return RuntimeResult(ok=False, reason=reason, message=message)


async def _stop_process(process: asyncio.subprocess.Process) -> None:
    """Stop a still-running run: ask politely, then insist (root §12)."""
    if process.returncode is not None:
        return
    process.terminate()
    try:
        await asyncio.wait_for(process.wait(), _KILL_GRACE_SECONDS)
    except TimeoutError:
        process.kill()
        await process.wait()


def _outcome_of(
    process: asyncio.subprocess.Process,
    stdout: bytes,
    stderr: bytes,
) -> RuntimeResult:
    """Translate a finished run's output into the contract's result.

    Details that help an operator — the exit code, the runtime's own error text,
    the tail of its diagnostics — are logged here and only here. A caller
    receives a fixed summary, never the runtime's wording (root §13).
    """
    record = _last_result_record(stdout)
    if record is None:
        logger.warning(
            "Hermes reported no result (exit_code=%s, stderr=%s).",
            process.returncode,
            stderr.decode("utf-8", errors="replace")[-_LOGGED_STDERR_LIMIT:],
        )
        return _failure(RuntimeFailureReason.FAILED, RUNTIME_FAILED_MESSAGE)
    if process.returncode != 0 or record.exit_code != 0 or record.error:
        logger.warning(
            "Hermes run failed (exit_code=%s, reported_exit_code=%s, error=%s).",
            process.returncode,
            record.exit_code,
            (record.error or "")[:_LOGGED_ERROR_LIMIT],
        )
        return _failure(RuntimeFailureReason.FAILED, RUNTIME_FAILED_MESSAGE)
    if record.text.strip() == "":
        # A run that claims success but produced nothing did not do the work,
        # and presenting it as an answer would misstate the outcome (§13).
        logger.warning("Hermes reported success without output.")
        return _failure(RuntimeFailureReason.FAILED, RUNTIME_FAILED_MESSAGE)
    return RuntimeResult(ok=True, output=record.text)


class HermesRuntimeAdapter:
    """``AgentRuntime`` implementation that runs one request through Hermes.

    An instance holds configuration only — no connection, no session, no
    process — so constructing one through the dependency costs nothing, and a
    missing or broken Hermes installation is discovered when a run is attempted,
    never at import or startup (root ``AGENTS.md`` §11).
    """

    def __init__(self, *, executable: str, timeout_seconds: float) -> None:
        self._executable = executable
        self._timeout_seconds = timeout_seconds

    async def execute(self, request: RuntimeRequest) -> RuntimeResult:
        """Run one request through Hermes and return its application-level outcome."""
        with tempfile.TemporaryDirectory(prefix="agentschat-run-") as workspace:
            return await self._execute_in(Path(workspace), request)

    async def _execute_in(
        self, workspace: Path, request: RuntimeRequest
    ) -> RuntimeResult:
        """Run inside an already-created workspace directory.

        The request's content reaches the runtime only through a file inside
        this directory: it is never part of the command line, so quotes,
        ``$(...)``, backticks, and leading dashes arrive verbatim and can never
        become arguments (root ``AGENTS.md`` §9, §10).
        """
        query_path = workspace / _QUERY_FILENAME
        query_path.write_text(request.content, encoding="utf-8")

        # Every flag is fixed here; the only varying argument is the workspace
        # path, and that comes from the operating system, never from a caller.
        argv: tuple[str, ...] = (
            self._executable,
            "chat",
            "--query-file",
            str(query_path),
            "--format",
            "stream-json",
            "--oneshot",
        )

        try:
            process = await asyncio.create_subprocess_exec(
                *argv,
                cwd=str(workspace),
                env=_child_environment(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError:
            logger.warning("Hermes could not be started.")
            return _failure(
                RuntimeFailureReason.UNAVAILABLE, RUNTIME_UNAVAILABLE_MESSAGE
            )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), self._timeout_seconds
            )
        except TimeoutError:
            logger.warning(
                "Hermes run exceeded its %s second limit and was stopped.",
                self._timeout_seconds,
            )
            await _stop_process(process)
            return _failure(RuntimeFailureReason.TIMED_OUT, RUNTIME_TIMED_OUT_MESSAGE)
        finally:
            # Reached on success, on timeout, and on cancellation: a run that is
            # no longer awaited must not outlive its caller (root AGENTS.md §12).
            if process.returncode is None:
                process.terminate()

        return _outcome_of(process, stdout, stderr)
