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
  ``result`` record, which is the only thing that is parsed for the outcome. Its
  earlier ``text`` records are genuine incremental output, so :meth:`stream`
  forwards each one as it is flushed rather than waiting for the run to end.

Everything else -- accounts, tenancy, quotas, retries, and the chat interface
that calls these methods -- belongs to the application and is deliberately absent
here (root ``AGENTS.md`` §5, §12, §21).
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from collections.abc import AsyncIterator
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
    RuntimeStreamEvent,
    RuntimeStreamEventKind,
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


async def _drain(stream: asyncio.StreamReader | None) -> bytes:
    """Read a pipe to EOF, so the child never blocks writing into a full buffer.

    Only used for stderr: a run that fills the stderr pipe while nobody is reading
    it would stall, and this task exists precisely so the adapter stops waiting
    for the child to finish before it starts reading its answer.
    """
    if stream is None:
        return b""
    try:
        return await stream.read()
    except (OSError, ValueError):
        return b""


async def _stderr_of(task: asyncio.Task[bytes]) -> bytes:
    """Collect what the stderr drain gathered, treating a cancelled drain as empty.

    Diagnostics are only ever used for a server-side log tail, so a drain that was
    cancelled (because the run ended early) contributes nothing rather than raising.
    """
    if not task.done() or task.cancelled():
        return b""
    if task.exception() is not None:
        return b""
    return task.result()


async def _lines(stream: asyncio.StreamReader) -> AsyncIterator[bytes]:
    """Yield one stdout line at a time, as Hermes flushes it.

    Reading line by line instead of waiting for the process to exit is what makes
    the run incremental: Hermes flushes every record as it is produced, so each
    line is available before the run is over.

    A line longer than the stream reader's limit raises, and the bytes stay in the
    buffer, so reading again would raise forever. Iteration stops there instead:
    the run then ends without a terminal record and is reported as a failure, which
    is honest about what was received rather than looping on a broken read.
    """
    while True:
        try:
            line = await stream.readline()
        except ValueError:
            logger.warning("Hermes produced a stdout line too long to read.")
            return
        if not line:
            return
        yield line


def _text_delta(line: bytes) -> str | None:
    """Return the text a ``text`` record carries, or None for anything else.

    ``--format stream-json`` interleaves ``system``/``text``/``tool_use``/
    ``tool_result``/``result`` records. Only ``text`` becomes a delta: the others
    carry no user-visible reply, and forwarding them would put Hermes's event
    vocabulary into the application's stream (root ``AGENTS.md`` §11).

    The delta's own whitespace is preserved verbatim -- only the surrounding line
    is trimmed for parsing -- because whitespace deltas are part of the answer and
    must reach the client byte for byte.
    """
    parsed_line = line.decode("utf-8", errors="replace").strip()
    if not parsed_line:
        return None
    try:
        record = json.loads(parsed_line)
    except json.JSONDecodeError:
        return None
    if not isinstance(record, dict) or record.get("type") != "text":
        return None
    value = record.get("text")
    if not isinstance(value, str) or value == "":
        return None
    return value


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
        try:
            process = await self._spawn(workspace, request)
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

    async def _spawn(
        self, workspace: Path, request: RuntimeRequest
    ) -> asyncio.subprocess.Process:
        """Start one Hermes run in `workspace`, writing the request to a file.

        Shared by the buffered and streaming paths so both invoke Hermes with the
        identical, fixed argument list, the identical isolated workspace, and the
        identical scrubbed environment. Every flag is fixed here; the only varying
        argument is the workspace path, which comes from the operating system and
        never from a caller.
        """
        query_path = workspace / _QUERY_FILENAME
        query_path.write_text(request.content, encoding="utf-8")

        argv: tuple[str, ...] = (
            self._executable,
            "chat",
            "--query-file",
            str(query_path),
            "--format",
            "stream-json",
            "--oneshot",
        )

        return await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(workspace),
            env=_child_environment(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    async def stream(
        self, request: RuntimeRequest
    ) -> AsyncIterator[RuntimeStreamEvent]:
        """Run one request, yielding the reply as Hermes produces it.

        The difference from :meth:`execute` is *when* the answer is read, not what
        is asked: same fixed argv, same private workspace, same scrubbed
        environment, same terminal ``result`` record. Here the child's stdout is
        read as it is flushed, so each ``text`` record becomes a delta immediately
        instead of after the run ends.
        """
        with tempfile.TemporaryDirectory(prefix="agentschat-run-") as workspace:
            async for event in self._stream_in(Path(workspace), request):
                yield event

    async def _stream_in(
        self, workspace: Path, request: RuntimeRequest
    ) -> AsyncIterator[RuntimeStreamEvent]:
        """Read one run's stdout incrementally and finish with one terminal event.

        Exactly one ``COMPLETED`` or ``FAILED`` event is always yielded last, so a
        consumer never has to guess whether a complete reply exists. Deltas may
        already have been forwarded when the run fails; the consumer's job is to
        show them as provisional and to persist nothing until the terminal event
        says the run succeeded (root ``AGENTS.md`` §10: the database represents
        completed responses only).
        """
        try:
            process = await self._spawn(workspace, request)
        except OSError:
            logger.warning("Hermes could not be started.")
            yield RuntimeStreamEvent(
                kind=RuntimeStreamEventKind.FAILED,
                reason=RuntimeFailureReason.UNAVAILABLE,
            )
            return

        # stderr is drained concurrently: a run that fills the stderr pipe while
        # nobody reads it would stall before its next line of stdout arrives.
        stderr_task = asyncio.create_task(_drain(process.stderr))
        collected = bytearray()
        try:
            try:
                async with asyncio.timeout(self._timeout_seconds):
                    assert process.stdout is not None
                    async for line in _lines(process.stdout):
                        collected += line
                        delta = _text_delta(line)
                        if delta is not None:
                            yield RuntimeStreamEvent(
                                kind=RuntimeStreamEventKind.DELTA, content=delta
                            )
                    await process.wait()
            except TimeoutError:
                logger.warning(
                    "Hermes run exceeded its %s second limit and was stopped.",
                    self._timeout_seconds,
                )
                await _stop_process(process)
                yield RuntimeStreamEvent(
                    kind=RuntimeStreamEventKind.FAILED,
                    reason=RuntimeFailureReason.TIMED_OUT,
                )
                return
        finally:
            # Also reached when the caller closes the stream early, which is what a
            # browser disconnect looks like: the child is terminated rather than
            # left running with nobody reading it (root AGENTS.md §11, §12).
            if not stderr_task.done():
                stderr_task.cancel()
            if process.returncode is None:
                process.terminate()

        # The full stdout was kept alongside the deltas so the existing outcome
        # logic decides success and failure in exactly one place.
        outcome = _outcome_of(process, bytes(collected), await _stderr_of(stderr_task))
        if outcome.ok:
            yield RuntimeStreamEvent(
                kind=RuntimeStreamEventKind.COMPLETED, content=outcome.output
            )
        else:
            yield RuntimeStreamEvent(
                kind=RuntimeStreamEventKind.FAILED,
                reason=outcome.reason or RuntimeFailureReason.FAILED,
            )
