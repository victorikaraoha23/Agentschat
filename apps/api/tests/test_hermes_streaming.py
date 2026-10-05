"""Adapter streaming: reading a Hermes run incrementally (Task 8.3).

Hermes's ``--format stream-json`` emits ``text`` records as it produces them and
ends with one ``result`` record. These tests feed that exact byte stream through
real ``asyncio.StreamReader`` objects, so the adapter's line-at-a-time reading is
exercised rather than simulated, while the subprocess itself stays faked: no
Hermes installation, no model, no network, no process started.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from app.hermes_adapter import HermesRuntimeAdapter
from app.runtime import (
    RuntimeFailureReason,
    RuntimeRequest,
    RuntimeStreamEvent,
    RuntimeStreamEventKind,
)

_EXECUTABLE = "hermes"


def _request(content: str = "Hello") -> RuntimeRequest:
    return RuntimeRequest(
        user_id=uuid.uuid4(), conversation_id=uuid.uuid4(), content=content
    )


def _adapter(timeout_seconds: float = 30.0) -> HermesRuntimeAdapter:
    return HermesRuntimeAdapter(executable=_EXECUTABLE, timeout_seconds=timeout_seconds)


def _line(record: dict[str, Any]) -> bytes:
    return (json.dumps(record) + "\n").encode()


def _success_stream(text: str, pieces: list[str]) -> bytes:
    """A realistic stream: init, text deltas, tool noise, then the result."""
    records: list[dict[str, Any]] = [
        {"type": "system", "subtype": "init", "model": "test", "session_id": "s"}
    ]
    records += [{"type": "text", "text": piece} for piece in pieces]
    records += [
        {"type": "tool_use", "name": "search", "input": {"q": "secret"}},
        {"type": "tool_result", "name": "search", "output": "private"},
    ]
    records += [
        {
            "type": "result",
            "session_id": "s",
            "exit_code": 0,
            "text": text,
            "tokens": {},
        }
    ]
    return b"".join(_line(record) for record in records)


class _FakeStreamProcess:
    """A process whose pipes are real readers over a prepared byte stream."""

    def __init__(
        self,
        stdout: bytes = b"",
        stderr: bytes = b"",
        returncode: int = 0,
        *,
        never_finishes: bool = False,
    ) -> None:
        self.stdout = asyncio.StreamReader()
        self.stderr = asyncio.StreamReader()
        self.returncode: int | None = None if never_finishes else returncode
        self._final_returncode = returncode
        self._never_finishes = never_finishes
        self.terminated = False
        self.killed = False

        if stdout:
            self.stdout.feed_data(stdout)
        self.stdout.feed_eof()
        if stderr:
            self.stderr.feed_data(stderr)
        self.stderr.feed_eof()

    async def wait(self) -> int:
        if self._never_finishes and not self.killed and not self.terminated:
            await asyncio.Event().wait()
        if self.returncode is None:
            self.returncode = self._final_returncode
        return int(self.returncode or 0)

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = -15

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9


def _fake_hermes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    stdout: bytes = b"",
    stderr: bytes = b"",
    returncode: int = 0,
    never_finishes: bool = False,
    spawn_error: OSError | None = None,
) -> list[_FakeStreamProcess]:
    """Replace the spawn call with a recorder that builds a prepared process.

    The process is built inside the spawned coroutine, not here: an
    ``asyncio.StreamReader`` binds to the running loop, and this helper runs
    before ``asyncio.run`` has started one.

    Returns the list the created processes land in, so a test can assert what
    happened to the child after the run.
    """
    created: list[_FakeStreamProcess] = []

    async def _create_subprocess_exec(*args: str, **kwargs: Any) -> _FakeStreamProcess:
        if spawn_error is not None:
            raise spawn_error
        process = _FakeStreamProcess(
            stdout, stderr, returncode, never_finishes=never_finishes
        )
        created.append(process)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _create_subprocess_exec)
    return created


async def _collect(runtime: HermesRuntimeAdapter) -> list[RuntimeStreamEvent]:
    """Drive the streaming contract from a synchronous test."""
    return [event async for event in runtime.stream(_request())]


# --- Incremental output ------------------------------------------------------


def test_text_records_become_deltas_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_hermes(
        monkeypatch, stdout=_success_stream("Hello there", ["Hel", "lo there"])
    )

    events = asyncio.run(_collect(_adapter()))

    assert [event.kind for event in events] == [
        RuntimeStreamEventKind.DELTA,
        RuntimeStreamEventKind.DELTA,
        RuntimeStreamEventKind.COMPLETED,
    ]
    assert [event.content for event in events[:2]] == ["Hel", "lo there"]


def test_the_run_completes_with_the_terminal_record_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_hermes(
        monkeypatch, stdout=_success_stream("Hello there", ["Hel", "lo there"])
    )

    events = asyncio.run(_collect(_adapter()))

    assert events[-1].kind is RuntimeStreamEventKind.COMPLETED
    assert events[-1].content == "Hello there"


def test_non_text_records_never_become_deltas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tool activity and session ids stay inside the adapter."""
    _fake_hermes(monkeypatch, stdout=_success_stream("Hi", ["Hi"]))

    events = asyncio.run(_collect(_adapter()))

    for event in events:
        assert "private" not in event.content
        assert "secret" not in event.content
        assert "session" not in event.content.lower()


def test_whitespace_deltas_are_preserved_verbatim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A whitespace-only delta is part of the answer and must survive."""
    _fake_hermes(monkeypatch, stdout=_success_stream("a b", ["a", " ", "b"]))

    events = asyncio.run(_collect(_adapter()))

    deltas = [e.content for e in events if e.kind is RuntimeStreamEventKind.DELTA]
    assert deltas == ["a", " ", "b"]


def test_a_malformed_line_is_skipped_and_the_run_still_completes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = _line({"type": "text", "text": "ok"}) + b"not json at all\n"
    body += _line({"type": "text", "text": "and more"})
    body += _line({"type": "result", "exit_code": 0, "text": "okand more"})
    _fake_hermes(monkeypatch, stdout=body)

    events = asyncio.run(_collect(_adapter()))

    assert events[-1].kind is RuntimeStreamEventKind.COMPLETED
    got = [e.content for e in events if e.kind is RuntimeStreamEventKind.DELTA]
    assert got == ["ok", "and more"]


def test_a_text_record_with_no_text_yields_no_delta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = _line({"type": "text"})
    body += _line({"type": "result", "exit_code": 0, "text": "Hi"})
    _fake_hermes(monkeypatch, stdout=body)

    events = asyncio.run(_collect(_adapter()))

    assert [e.kind for e in events] == [RuntimeStreamEventKind.COMPLETED]


async def _collect(runtime: HermesRuntimeAdapter) -> list[RuntimeStreamEvent]:
    return [event async for event in runtime.stream(_request())]


# --- Failure translation -----------------------------------------------------


def test_a_failing_run_ends_with_a_failed_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = _line({"type": "text", "text": "partial"})
    body += _line({"type": "result", "exit_code": 1, "error": "boom"})
    _fake_hermes(monkeypatch, stdout=body, returncode=1)

    events = asyncio.run(_collect(_adapter()))

    assert events[-1].kind is RuntimeStreamEventKind.FAILED
    assert events[-1].reason is RuntimeFailureReason.FAILED


def test_partial_output_before_a_failure_is_still_forwarded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The adapter reports what arrived; deciding what to store is not its job."""
    body = _line({"type": "text", "text": "partial"})
    body += _line({"type": "result", "exit_code": 1, "error": "boom"})
    _fake_hermes(monkeypatch, stdout=body, returncode=1)

    events = asyncio.run(_collect(_adapter()))

    assert [e.kind for e in events] == [
        RuntimeStreamEventKind.DELTA,
        RuntimeStreamEventKind.FAILED,
    ]


def test_hermes_error_text_never_reaches_the_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = _line({
        "type": "result",
        "exit_code": 1,
        "error": "hermes exited 1 at /home/hermes/.hermes/trace tok=sk-secret",
    })
    _fake_hermes(monkeypatch, stdout=body, returncode=1)

    events = asyncio.run(_collect(_adapter()))

    rendered = " ".join(event.content for event in events)
    assert "sk-secret" not in rendered
    assert "/home/hermes" not in rendered


def test_success_without_output_is_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A run that claims success but says nothing did not do the work."""
    _fake_hermes(
        monkeypatch, stdout=_line({"type": "result", "exit_code": 0, "text": ""})
    )

    events = asyncio.run(_collect(_adapter()))

    assert [e.kind for e in events] == [RuntimeStreamEventKind.FAILED]


def test_a_run_with_no_result_record_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_hermes(monkeypatch, stdout=_line({"type": "text", "text": "hi"}))

    events = asyncio.run(_collect(_adapter()))

    assert events[-1].kind is RuntimeStreamEventKind.FAILED


def test_an_unstartable_hermes_reports_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_hermes(monkeypatch, spawn_error=OSError("no such file"))

    events = asyncio.run(_collect(_adapter()))

    assert [e.kind for e in events] == [RuntimeStreamEventKind.FAILED]
    assert events[0].reason is RuntimeFailureReason.UNAVAILABLE


def test_a_run_over_its_time_limit_is_stopped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _fake_hermes(
        monkeypatch,
        stdout=_line({"type": "text", "text": "half an answer"}),
        never_finishes=True,
    )

    events = asyncio.run(_collect(_adapter(timeout_seconds=0.05)))

    assert events[-1].kind is RuntimeStreamEventKind.FAILED
    assert events[-1].reason is RuntimeFailureReason.TIMED_OUT
    assert created and (created[0].terminated or created[0].killed)


# --- Isolation is unchanged by streaming -------------------------------------


def test_streaming_uses_the_same_fixed_command_and_scrubbed_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: dict[str, Any] = {}

    async def _create_subprocess_exec(*args: str, **kwargs: Any) -> _FakeStreamProcess:
        recorded["argv"] = tuple(args)
        recorded["env"] = dict(kwargs["env"])
        recorded["cwd"] = str(kwargs["cwd"])
        recorded["query"] = (Path(recorded["cwd"]) / "query.txt").read_text(
            encoding="utf-8"
        )
        return _FakeStreamProcess(_success_stream("Hi", ["Hi"]))

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _create_subprocess_exec)

    asyncio.run(_collect(_adapter()))

    argv = recorded["argv"]
    assert argv[1:4] == ("chat", "--query-file", argv[3])
    assert argv[4:] == ("--format", "stream-json", "--oneshot")
    assert recorded["query"] == "Hello"
    assert not any(name.upper().startswith("AGENTSCHAT_") for name in recorded["env"])


def test_the_user_text_never_reaches_the_command_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hostile = "--query-file=/etc/passwd; rm -rf /"
    recorded: dict[str, Any] = {}

    async def _create_subprocess_exec(*args: str, **kwargs: Any) -> _FakeStreamProcess:
        recorded["argv"] = tuple(args)
        return _FakeStreamProcess(_success_stream("ok", ["ok"]))

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _create_subprocess_exec)

    async def _run_hostile() -> None:
        async for _ in _adapter().stream(_request(hostile)):
            pass

    asyncio.run(_run_hostile())

    assert hostile not in " ".join(recorded["argv"])
