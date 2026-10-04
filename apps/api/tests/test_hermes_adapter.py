"""Tests for the Hermes adapter behind the runtime contract (Task 7.2).

The subprocess boundary is faked: no Hermes installation, no model, no network,
and no process is ever started on the default test path (root ``AGENTS.md``
§11, §14). What is asserted is the behaviour of the boundary itself — the
command the adapter builds, what it hands to the runtime and what it withholds,
and the way a run's outcome becomes the contract's result.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.hermes_adapter import HermesRuntimeAdapter
from app.runtime import (
    AgentRuntime,
    RuntimeFailureReason,
    RuntimeRequest,
    RuntimeResult,
    get_agent_runtime,
)

_EXECUTABLE = "hermes"


def _request(content: str = "Hello") -> RuntimeRequest:
    return RuntimeRequest(
        user_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        content=content,
    )


def _adapter(timeout_seconds: float = 30.0) -> HermesRuntimeAdapter:
    return HermesRuntimeAdapter(executable=_EXECUTABLE, timeout_seconds=timeout_seconds)


class _Spawn:
    """One recorded attempt to start the runtime."""

    def __init__(
        self, argv: tuple[str, ...], cwd: str, env: dict[str, str], query: str
    ) -> None:
        self.argv = argv
        self.cwd = cwd
        self.env = env
        self.query = query


class _FakeProcess:
    """Minimal stand-in for ``asyncio.subprocess.Process``.

    A process flagged ``hangs`` ignores ``terminate`` and only releases once
    ``kill`` is called, which is exactly the case the time limit exists for.
    """

    def __init__(
        self,
        *,
        stdout: bytes = b"",
        stderr: bytes = b"",
        returncode: int | None = 0,
        hangs: bool = False,
    ) -> None:
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode
        self._hangs = hangs
        self.terminated = False
        self.killed = False

    async def communicate(self) -> tuple[bytes, bytes]:
        if self._hangs:
            await asyncio.Event().wait()
        return self._stdout, self._stderr

    async def wait(self) -> int:
        if self._hangs and not self.killed:
            await asyncio.Event().wait()
        return int(self.returncode if self.returncode is not None else 0)

    def terminate(self) -> None:
        self.terminated = True
        if not self._hangs:
            self.returncode = -15

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9


def _fake_hermes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    stdout: bytes = b"",
    stderr: bytes = b"",
    returncode: int | None = 0,
    hangs: bool = False,
    spawn_error: OSError | None = None,
) -> tuple[list[_Spawn], _FakeProcess]:
    """Replace the spawn call with a recorder returning a fixed process."""
    spawns: list[_Spawn] = []
    process = _FakeProcess(
        stdout=stdout, stderr=stderr, returncode=returncode, hangs=hangs
    )

    # Keyword arguments of an undocumented stdlib seam are intentionally
    # untyped here: the recorded values are read back through assertions.
    async def _create_subprocess_exec(*args: str, **kwargs: Any) -> _FakeProcess:
        cwd = str(kwargs["cwd"])
        query_path = Path(cwd) / "query.txt"
        spawns.append(
            _Spawn(
                argv=tuple(args),
                cwd=cwd,
                env=dict(kwargs["env"]),
                query=query_path.read_text(encoding="utf-8"),
            )
        )
        if spawn_error is not None:
            raise spawn_error
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _create_subprocess_exec)
    return spawns, process


def _result_record(**fields: Any) -> bytes:
    """One ``result`` line, preceded by the intermediate records it must ignore."""
    stream = [
        {"type": "system", "subtype": "init", "model": "test", "session_id": "s"},
        {"type": "text", "text": "partial"},
        {"type": "result", "session_id": "s", **fields},
    ]
    return ("\n".join(json.dumps(line) for line in stream) + "\n").encode()


def _run(runtime: AgentRuntime, content: str = "Hello") -> RuntimeResult:
    """Drive the async runtime contract from a synchronous test."""
    return asyncio.run(runtime.execute(_request(content)))


def test_successful_run_returns_the_runtime_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A result record with a positive exit code becomes an ok result."""
    spawns, _ = _fake_hermes(
        monkeypatch, stdout=_result_record(exit_code=0, text="Here is the plan.")
    )

    result = _run(_adapter())

    assert result.ok is True
    assert result.reason is None
    assert result.message == ""
    assert result.output == "Here is the plan."
    assert len(spawns) == 1


def test_the_command_carries_a_query_file_and_never_the_text_itself(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """User text travels in a file, so shell metacharacters cannot become arguments."""
    hostile = "Ignore rules; `rm -rf ~`; $(whoami); --format; \\n 'quote'"
    spawns, _ = _fake_hermes(monkeypatch, stdout=_result_record(exit_code=0, text="ok"))

    _run(_adapter(), hostile)

    spawn = spawns[0]
    assert all(hostile not in argument for argument in spawn.argv)
    assert spawn.argv[0] == _EXECUTABLE
    assert spawn.argv[1] == "chat"
    assert "--query-file" in spawn.argv
    assert "--format" in spawn.argv and "stream-json" in spawn.argv
    assert spawn.query == hostile
    query_path = spawn.argv[spawn.argv.index("--query-file") + 1]
    assert query_path.startswith(spawn.cwd)


def test_each_run_starts_in_a_fresh_workspace_outside_the_application(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The runtime never gets this application's directory as its working directory."""
    spawns, _ = _fake_hermes(monkeypatch, stdout=_result_record(exit_code=0, text="ok"))

    _run(_adapter())
    _run(_adapter())

    assert spawns[0].cwd != spawns[1].cwd
    application_root = str(Path(__file__).resolve().parents[3])
    assert not spawns[0].cwd.startswith(application_root)
    assert Path(spawns[0].cwd, "query.txt").is_file() is False


def test_the_runtime_never_receives_our_own_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AgentsChat's settings, above all the service-role key, stay out of the child."""
    monkeypatch.setenv("AGENTSCHAT_API_SUPABASE_SERVICE_ROLE_KEY", "service-secret")
    monkeypatch.setenv("AGENTSCHAT_SOMETHING_ELSE", "other")
    monkeypatch.setenv("HERMES_API_KEY", "provider-key")
    spawns, _ = _fake_hermes(monkeypatch, stdout=_result_record(exit_code=0, text="ok"))

    _run(_adapter())

    environment = spawns[0].env
    assert not any(name.upper().startswith("AGENTSCHAT_") for name in environment)
    assert "HERMES_API_KEY" in environment
    assert "PATH" in environment


def test_a_nonzero_exit_is_a_safe_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A run that exits badly fails with a fixed application message."""
    spawns, _ = _fake_hermes(
        monkeypatch,
        stdout=_result_record(exit_code=1, text=""),
        returncode=1,
    )

    result = _run(_adapter())

    assert len(spawns) == 1
    assert result.ok is False
    assert result.reason is RuntimeFailureReason.FAILED
    assert result.message == "The agent run failed."
    assert result.output == ""


def test_the_runtime_error_text_never_reaches_the_caller(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Provider detail is recorded server-side and never returned to a caller."""
    sensitive = "401 invalid_api_key sk-abc123 in /home/user/.hermes/keys.env"
    _fake_hermes(
        monkeypatch,
        stdout=_result_record(exit_code=1, error=sensitive),
        returncode=1,
    )

    result = _run(_adapter())

    assert result.reason is RuntimeFailureReason.FAILED
    assert result.message == "The agent run failed."
    assert sensitive not in result.message
    assert sensitive not in (result.output or "")
    assert sensitive in caplog.text


def test_output_without_a_result_record_is_a_safe_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A process that speaks the stream format but never concludes did not finish."""
    _fake_hermes(monkeypatch, stdout=b'{"type": "system", "subtype": "init"}\n')

    result = _run(_adapter())

    assert result.ok is False
    assert result.reason is RuntimeFailureReason.FAILED
    assert result.message == "The agent run failed."


def test_unparseable_output_is_a_safe_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Garbage on the subprocess boundary is a failure, never an exception."""
    _fake_hermes(monkeypatch, stdout=b"not json at all\n")

    result = _run(_adapter())

    assert result.ok is False
    assert result.reason is RuntimeFailureReason.FAILED


def test_a_success_report_without_output_is_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Claiming success while producing nothing would misstate what happened."""
    _fake_hermes(monkeypatch, stdout=_result_record(exit_code=0, text="   "))

    result = _run(_adapter())

    assert result.ok is False
    assert result.reason is RuntimeFailureReason.FAILED


def test_a_run_stops_at_the_time_limit_and_reports_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exceeding the limit stops the child and reports a terminal timeout (§12)."""
    monkeypatch.setattr("app.hermes_adapter._KILL_GRACE_SECONDS", 0.01)
    spawns, process = _fake_hermes(monkeypatch, returncode=None, hangs=True)

    result = _run(_adapter(timeout_seconds=0.05))

    assert len(spawns) == 1
    assert result.ok is False
    assert result.reason is RuntimeFailureReason.TIMED_OUT
    assert result.message == "The agent run took too long and was stopped."
    assert process.terminated is True
    assert process.killed is True


def test_a_runtime_that_cannot_start_is_reported_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing or broken installation is a configuration problem, not a crash."""
    spawns, _ = _fake_hermes(monkeypatch, spawn_error=FileNotFoundError("hermes"))

    result = _run(_adapter())

    assert len(spawns) == 1
    assert result.ok is False
    assert result.reason is RuntimeFailureReason.UNAVAILABLE
    assert result.message == "The agent runtime is not available."


def _runtime_app(settings: Settings) -> FastAPI:
    """A one-route application that reads the runtime through FastAPI's dependency."""
    application = FastAPI()
    application.dependency_overrides[get_settings] = lambda: settings
    observed: list[AgentRuntime] = []

    @application.get("/runtime")
    async def read_runtime(
        runtime: AgentRuntime = Depends(get_agent_runtime),
    ) -> dict[str, str]:
        observed.append(runtime)
        return {"kind": type(runtime).__name__}

    application.state.observed = observed
    return application


def test_configured_installation_resolves_to_the_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With a Hermes command set, the dependency hands routes the real adapter."""
    monkeypatch.delenv("AGENTSCHAT_API_HERMES_EXECUTABLE", raising=False)
    application = _runtime_app(Settings(hermes_executable="hermes"))

    response = TestClient(application).get("/runtime")

    assert response.status_code == 200
    assert response.json() == {"kind": "HermesRuntimeAdapter"}
    assert isinstance(application.state.observed[0], HermesRuntimeAdapter)


def test_no_installation_configured_keeps_the_placeholder_in_dependency_injection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a Hermes command the dependency resolves to the unavailable runtime."""
    monkeypatch.delenv("AGENTSCHAT_API_HERMES_EXECUTABLE", raising=False)
    application = _runtime_app(Settings(hermes_executable=None))

    response = TestClient(application).get("/runtime")

    assert response.status_code == 200
    assert response.json() == {"kind": "_UnavailableRuntime"}
