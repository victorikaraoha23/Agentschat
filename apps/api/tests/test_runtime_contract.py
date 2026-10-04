"""Contract tests for the agent runtime boundary (Task 7.1).

Covers the request/result shapes, the fake success and failure runtimes,
dependency-injection substitution without Hermes imports, and safe failure
representation. Touches only the contract and the fakes; no agent runs.
"""

import asyncio
import uuid

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.runtime import (
    AgentRuntime,
    RuntimeFailureReason,
    RuntimeRequest,
    RuntimeResult,
    get_agent_runtime,
)
from tests.fake_runtime import FakeFailureRuntime, FakeSuccessRuntime


def _request(content: str = "Hello") -> RuntimeRequest:
    return RuntimeRequest(
        user_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        content=content,
    )


def test_request_requires_nonblank_content_within_limit() -> None:
    with pytest.raises(ValidationError):
        _request(content="   ")
    with pytest.raises(ValidationError):
        _request(content="x" * 4001)
    assert _request(content="  Hello  ").content == "Hello"


def test_success_result_rejects_failure_shape() -> None:
    with pytest.raises(ValidationError):
        RuntimeResult(ok=True, output="x", reason=RuntimeFailureReason.FAILED)


def test_failure_result_requires_a_reason() -> None:
    with pytest.raises(ValidationError):
        RuntimeResult(ok=False, message="short summary")


def test_success_result_carries_output() -> None:
    result = RuntimeResult(ok=True, output="draft reply")
    assert result.ok is True
    assert result.output == "draft reply"
    assert result.reason is None


def test_failure_result_carries_only_safe_categories() -> None:
    for reason in RuntimeFailureReason:
        result = RuntimeResult(ok=False, reason=reason, message="short summary")
        assert result.ok is False
        assert result.reason is reason


def test_fake_success_runtime_returns_output() -> None:
    runtime = FakeSuccessRuntime(output="hello from the fake")
    result = asyncio.run(runtime.execute(_request()))
    assert result.ok is True
    assert result.output == "hello from the fake"
    assert len(runtime.requests) == 1


def test_fake_failure_runtime_returns_safe_failure() -> None:
    runtime = FakeFailureRuntime(reason=RuntimeFailureReason.TIMED_OUT)
    result = asyncio.run(runtime.execute(_request()))
    assert result.ok is False
    assert result.reason is RuntimeFailureReason.TIMED_OUT
    assert result.message == "Fake runtime failure."


def test_app_code_receives_fake_runtime_through_dependency() -> None:
    """Overriding the dependency swaps implementations with no Hermes import."""

    app = FastAPI()

    @app.get("/fake-runtime-check")
    def check(runtime: AgentRuntime = Depends(get_agent_runtime)) -> dict[str, bool]:
        return {"ok": asyncio.run(runtime.execute(_request())).ok}

    fake = FakeSuccessRuntime()
    app.dependency_overrides[get_agent_runtime] = lambda: fake
    try:
        response = TestClient(app).get("/fake-runtime-check")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert len(fake.requests) == 1


def test_default_runtime_reports_unavailable_without_hermes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no Hermes command configured, runs answer unavailable and nothing starts."""
    monkeypatch.delenv("AGENTSCHAT_API_HERMES_EXECUTABLE", raising=False)

    result = asyncio.run(get_agent_runtime(Settings()).execute(_request()))

    assert result.ok is False
    assert result.reason is RuntimeFailureReason.UNAVAILABLE
    assert result.message == "The agent runtime is not available."
