"""Execution: POST /conversations/{conversation_id}/execute (Task 8.1).

The first end-to-end path from an authenticated API request into the agent
runtime. Neither Supabase nor Hermes appears here: the message store and the
runtime are swapped through the application's own dependency seams, so these
tests prove authentication, ownership, validation, persistence-before-execution,
one-run-per-request, and safe failure translation without a database or a
running Hermes instance.
"""

from __future__ import annotations

from threading import get_ident
from typing import Protocol
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from app.auth import AuthenticatedUser, get_access_token_verifier
from app.config import Settings, get_settings
from app.main import MAX_MESSAGE_CONTENT_LENGTH, app, get_message_store
from app.messages import Message, MessageCreateError
from app.runtime import (
    RUNTIME_FAILED_MESSAGE,
    RUNTIME_INVALID_REQUEST_MESSAGE,
    RUNTIME_TIMED_OUT_MESSAGE,
    RUNTIME_UNAVAILABLE_MESSAGE,
    RuntimeFailureReason,
    RuntimeRequest,
    RuntimeResult,
    get_agent_runtime,
)
from tests.fake_runtime import FakeFailureRuntime, FakeSuccessRuntime

USER_ID = "123e4567-e89b-12d3-a456-426614174000"
OTHER_USER_ID = "123e4567-e89b-12d3-a456-426614174999"
CONVERSATION_ID = "223e4567-e89b-12d3-a456-426614174000"

EXECUTE_PATH = "/conversations/{conversation_id}/execute"

CREATED_ROW: dict[str, object] = {
    "id": "323e4567-e89b-12d3-a456-426614174000",
    "conversation_id": CONVERSATION_ID,
    "user_id": USER_ID,
    "role": "user",
    "content": "Hello",
    "created_at": "2026-10-04T12:00:00Z",
}

ASSISTANT_ROW_ID = "423e4567-e89b-12d3-a456-426614174000"


class RuntimeProbe(Protocol):
    """The runtime seam the endpoint exercises: recorded requests, one outcome."""

    requests: list[RuntimeRequest]

    async def execute(self, request: RuntimeRequest) -> RuntimeResult:
        """Answer one execution."""
        ...  # pragma: no cover - protocol only


class FakeVerifier:
    """Stand-in for the token verifier: accepts one bearer token."""

    def __init__(self, user_id: str) -> None:
        """Bind the verifier to the identity a valid token resolves to."""
        self._user_id = user_id

    def verify(self, access_token: str) -> AuthenticatedUser:
        """Accept the canned token and return the bound identity."""
        assert access_token == "header.payload.signature"
        return AuthenticatedUser(user_id=self._user_id)


class FakeMessageStore:
    """Stand-in for the message store: records writes, replays a row.

    Ownership is answered exactly as the real store answers it: a conversation
    the caller does not own (or one that does not exist) yields `None`, so the
    endpoint must treat both as the same 404.
    """

    def __init__(
        self,
        owns_conversation: bool = True,
        error: Exception | None = None,
        assistant_error: Exception | None = None,
        assistant_missing: bool = False,
    ) -> None:
        """Decide whether the caller owns the conversation, or raise an error."""
        self._owns_conversation = owns_conversation
        self._error = error
        self.writes: list[tuple[str, str, str]] = []
        self.assistant_writes: list[tuple[str, str, str]] = []
        self._assistant_error = assistant_error
        self._assistant_missing = assistant_missing

    def create_for_user(
        self, user_id: str, conversation_id: str, content: str
    ) -> Message | None:
        """Record the write; answer `None` for a conversation the caller lacks."""
        self.writes.append((user_id, conversation_id, content))
        if self._error is not None:
            raise self._error
        if not self._owns_conversation:
            return None
        return Message.model_validate({
            **CREATED_ROW,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "content": content,
        })

    def create_assistant_for_user(
        self, user_id: str, conversation_id: str, content: str
    ) -> Message | None:
        """Record the reply under the same ownership answer as the user write."""
        self.assistant_writes.append((user_id, conversation_id, content))
        if self._assistant_error is not None:
            raise self._assistant_error
        if not self._owns_conversation or self._assistant_missing:
            return None
        return Message.model_validate({
            **CREATED_ROW,
            "id": ASSISTANT_ROW_ID,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "role": "assistant",
            "content": content,
        })


class PersistFirstRuntime(FakeSuccessRuntime):
    """Captures what the store had already written at the moment execution started."""

    def __init__(self, store: FakeMessageStore) -> None:
        """Watch ``store`` so the test proves ordering, not just both outcomes."""
        super().__init__()
        self._store = store
        self.writes_at_execute: list[tuple[str, str, str]] = []

    async def execute(self, request: RuntimeRequest) -> RuntimeResult:
        """Snapshot the store's writes before answering successfully."""
        self.writes_at_execute = list(self._store.writes)
        return await super().execute(request)


def execute_message(
    monkeypatch: pytest.MonkeyPatch,
    body: object,
    *,
    user_id: str = USER_ID,
    conversation_id: str = CONVERSATION_ID,
    store: FakeMessageStore | None = None,
    runtime: RuntimeProbe | None = None,
    authenticated: bool = True,
) -> tuple[FakeMessageStore, RuntimeProbe, Response]:
    """POST to the execute endpoint with faked auth, store, and runtime.

    Returns the three handles assertions need: the store (what was persisted),
    the runtime (what it was asked), and the HTTP response.
    """
    active_store = store if store is not None else FakeMessageStore()
    active_runtime: RuntimeProbe = (
        runtime if runtime is not None else FakeSuccessRuntime()
    )
    if authenticated:
        monkeypatch.setitem(
            app.dependency_overrides,
            get_access_token_verifier,
            lambda: FakeVerifier(user_id),
        )
    monkeypatch.setitem(
        app.dependency_overrides, get_message_store, lambda: active_store
    )
    monkeypatch.setitem(
        app.dependency_overrides, get_agent_runtime, lambda: active_runtime
    )
    headers = (
        {"Authorization": "Bearer header.payload.signature"} if authenticated else None
    )
    response = TestClient(app, raise_server_exceptions=False).post(
        f"/conversations/{conversation_id}/execute",
        json=body,
        headers=headers,
    )
    return active_store, active_runtime, response


# --- Authentication ---------------------------------------------------------


def test_execute_route_exists() -> None:
    """The execution route is registered on the conversation path, POST only."""
    routes = {
        (route.path, method)
        for route in app.routes
        if hasattr(route, "path") and hasattr(route, "methods")
        for method in route.methods
    }

    assert (EXECUTE_PATH, "POST") in routes


def test_unauthenticated_request_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """No bearer token means 401, with nothing persisted and nothing executed."""
    store, runtime, response = execute_message(
        monkeypatch, {"content": "Hello"}, authenticated=False
    )

    assert response.status_code == 401
    assert store.writes == []
    assert runtime.requests == []


def test_authenticated_request_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """A verified caller gets the runtime's output back as the typed result."""
    _store, runtime, response = execute_message(monkeypatch, {"content": "Hello"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["content"] == "fake assistant reply"
    assert payload["message_id"] == ASSISTANT_ROW_ID
    assert len(runtime.requests) == 1


def test_client_supplied_identity_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    """A `user_id` in the body cannot move the run: identity comes from the token."""
    _store, runtime, response = execute_message(
        monkeypatch,
        {"content": "Hello", "user_id": OTHER_USER_ID},
    )

    assert response.status_code == 200
    assert runtime.requests[0].user_id == UUID(USER_ID)


# --- Ownership --------------------------------------------------------------


def test_user_can_execute_in_their_own_conversation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The owner's message is persisted and the run receives both identities."""
    store, runtime, response = execute_message(monkeypatch, {"content": "Hello"})

    assert response.status_code == 200
    assert store.writes == [(USER_ID, CONVERSATION_ID, "Hello")]
    assert store.assistant_writes == [
        (USER_ID, CONVERSATION_ID, "fake assistant reply")
    ]
    request = runtime.requests[0]
    assert request.user_id == UUID(USER_ID)
    assert request.conversation_id == UUID(CONVERSATION_ID)


def test_user_cannot_execute_in_another_users_conversation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A foreign conversation is a 404 and the runtime never runs."""
    store, runtime, response = execute_message(
        monkeypatch,
        {"content": "Hello"},
        user_id=OTHER_USER_ID,
        store=FakeMessageStore(owns_conversation=False),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Conversation not found."}
    assert runtime.requests == []
    # The attempted write named the intruder as its author, never the owner.
    assert store.writes == [(OTHER_USER_ID, CONVERSATION_ID, "Hello")]


def test_missing_and_foreign_conversations_answer_identically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both are indistinguishable: same status, same body, no execution."""
    responses: list[Response] = []
    for _ in range(2):
        _store, runtime, response = execute_message(
            monkeypatch,
            {"content": "Hello"},
            store=FakeMessageStore(owns_conversation=False),
        )
        assert runtime.requests == []
        responses.append(response)

    assert responses[0].status_code == responses[1].status_code == 404
    assert responses[0].json() == responses[1].json()


def test_invalid_conversation_id_is_rejected_before_anything_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A malformed path id is refused by validation before persistence or execution."""
    store, runtime, response = execute_message(
        monkeypatch, {"content": "Hello"}, conversation_id="not-a-uuid"
    )

    assert response.status_code == 422
    assert store.writes == []
    assert runtime.requests == []


# --- Validation -------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"content": ""},
        {"content": "x" * (MAX_MESSAGE_CONTENT_LENGTH + 1)},
    ],
    ids=["missing", "empty", "overlong"],
)
def test_invalid_content_is_rejected_before_persisting_or_executing(
    monkeypatch: pytest.MonkeyPatch,
    body: object,
) -> None:
    """The message endpoint's rules apply unchanged: nothing runs on bad input."""
    store, runtime, response = execute_message(monkeypatch, body)

    assert response.status_code == 422
    assert store.writes == []
    assert runtime.requests == []


def test_whitespace_only_content_is_rejected_with_the_existing_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Whitespace-only content gets the same 422 as the message endpoint."""
    store, runtime, response = execute_message(monkeypatch, {"content": "   \t "})

    assert response.status_code == 422
    assert "Content must not be blank." in response.text
    assert store.writes == []
    assert runtime.requests == []


def test_valid_content_survives_round_trip_intact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """What the user typed (minus surrounding whitespace) is what is stored and run."""
    store, runtime, response = execute_message(monkeypatch, {"content": "  Hello  "})

    assert response.status_code == 200
    assert store.writes == [(USER_ID, CONVERSATION_ID, "Hello")]
    assert runtime.requests[0].content == "Hello"


# --- Persistence ------------------------------------------------------------


def test_persistence_runs_outside_the_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Synchronous persistence runs on a worker; runtime execution stays async."""
    persistence_threads: list[int] = []
    runtime_threads: list[int] = []

    class ThreadRecordingStore(FakeMessageStore):
        def create_for_user(
            self, user_id: str, conversation_id: str, content: str
        ) -> Message | None:
            persistence_threads.append(get_ident())
            return super().create_for_user(user_id, conversation_id, content)

        def create_assistant_for_user(
            self, user_id: str, conversation_id: str, content: str
        ) -> Message | None:
            persistence_threads.append(get_ident())
            return super().create_assistant_for_user(user_id, conversation_id, content)

    class ThreadRecordingRuntime(FakeSuccessRuntime):
        async def execute(self, request: RuntimeRequest) -> RuntimeResult:
            runtime_threads.append(get_ident())
            return await super().execute(request)

    store, _runtime, response = execute_message(
        monkeypatch,
        {"content": "Hello"},
        store=ThreadRecordingStore(),
        runtime=ThreadRecordingRuntime(),
    )

    assert response.status_code == 200
    assert store.writes == [(USER_ID, CONVERSATION_ID, "Hello")]
    assert len(persistence_threads) == 2
    assert len(runtime_threads) == 1
    assert all(thread != runtime_threads[0] for thread in persistence_threads)


def test_message_is_persisted_before_the_runtime_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ordering, not just both outcomes: the row exists when execution starts."""
    store = FakeMessageStore()
    runtime = PersistFirstRuntime(store)

    _store, _runtime, response = execute_message(
        monkeypatch, {"content": "Hello"}, store=store, runtime=runtime
    )

    assert response.status_code == 200
    assert runtime.writes_at_execute == [(USER_ID, CONVERSATION_ID, "Hello")]


def test_failed_store_write_never_reaches_the_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A persistence failure answers the existing fixed 503 without executing."""
    store, runtime, response = execute_message(
        monkeypatch,
        {"content": "Hello"},
        store=FakeMessageStore(error=MessageCreateError()),
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "The message could not be sent."}
    assert runtime.requests == []


# --- Runtime outcomes -------------------------------------------------------


@pytest.mark.parametrize(
    ("reason", "expected_status", "expected_detail"),
    [
        (RuntimeFailureReason.FAILED, 502, RUNTIME_FAILED_MESSAGE),
        (RuntimeFailureReason.UNAVAILABLE, 503, RUNTIME_UNAVAILABLE_MESSAGE),
        (RuntimeFailureReason.TIMED_OUT, 504, RUNTIME_TIMED_OUT_MESSAGE),
        (RuntimeFailureReason.INVALID_REQUEST, 400, RUNTIME_INVALID_REQUEST_MESSAGE),
    ],
    ids=["failed", "unavailable", "timed-out", "invalid-request"],
)
def test_runtime_failure_becomes_a_safe_api_error(
    monkeypatch: pytest.MonkeyPatch,
    reason: RuntimeFailureReason,
    expected_status: int,
    expected_detail: str,
) -> None:
    """Every failure reason maps to a fixed status and detail, never runtime prose."""
    store, runtime, response = execute_message(
        monkeypatch, {"content": "Hello"}, runtime=FakeFailureRuntime(reason=reason)
    )

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}
    # The fake's own wording is absent: the endpoint never relays it.
    assert "Fake runtime failure." not in response.text
    # The user's message is still the only row written — persisted before the
    # run, never deleted by its failure, and no assistant message invented.
    assert store.writes == [(USER_ID, CONVERSATION_ID, "Hello")]
    assert len(runtime.requests) == 1


def test_runtime_internals_never_reach_the_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provider wording, paths, and secrets in a runtime message stay server-side."""

    class LeakProneRuntime:
        """A runtime that hands back exactly what a caller must never see."""

        def __init__(self) -> None:
            self.requests: list[RuntimeRequest] = []

        async def execute(self, request: RuntimeRequest) -> RuntimeResult:
            self.requests.append(request)
            return RuntimeResult(
                ok=False,
                reason=RuntimeFailureReason.FAILED,
                message="hermes exited 1 at /home/hermes/.hermes/trace tok=sk-secret",
            )

    store, _runtime, response = execute_message(
        monkeypatch, {"content": "Hello"}, runtime=LeakProneRuntime()
    )

    assert response.status_code == 502
    assert response.json() == {"detail": RUNTIME_FAILED_MESSAGE}
    for leaked in (
        "hermes",
        "exited 1",
        "/home/hermes",
        "tok=",
        "sk-secret",
        "Traceback",
    ):
        assert leaked not in response.text
    # The conversation still holds exactly the user's own message.
    assert store.writes == [(USER_ID, CONVERSATION_ID, "Hello")]


def test_exactly_one_run_happens_per_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """No automatic retry or duplicate execution inside one HTTP request."""
    _store, runtime, response = execute_message(monkeypatch, {"content": "Hello"})

    assert response.status_code == 200
    assert len(runtime.requests) == 1


def test_execution_uses_the_real_runtime_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a runtime override the production dependency decides the outcome.

    With Hermes unconfigured, ``get_agent_runtime`` yields the unavailable
    placeholder, so the endpoint answers the contract's fixed 503 and no
    Hermes process is ever started.
    """
    monkeypatch.delenv("AGENTSCHAT_API_HERMES_EXECUTABLE", raising=False)
    monkeypatch.delenv("AGENTSCHAT_API_SUPABASE_URL", raising=False)
    monkeypatch.delenv("AGENTSCHAT_API_SUPABASE_SERVICE_ROLE_KEY", raising=False)
    store = FakeMessageStore()
    monkeypatch.setitem(
        app.dependency_overrides,
        get_access_token_verifier,
        lambda: FakeVerifier(USER_ID),
    )
    monkeypatch.setitem(app.dependency_overrides, get_message_store, lambda: store)
    # Freshly built settings (environment cleared above) are what the runtime
    # dependency reads, so the outcome never depends on ambient variables.
    monkeypatch.setitem(app.dependency_overrides, get_settings, lambda: Settings())

    response = TestClient(app, raise_server_exceptions=False).post(
        f"/conversations/{CONVERSATION_ID}/execute",
        json={"content": "Hello"},
        headers={"Authorization": "Bearer header.payload.signature"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": RUNTIME_UNAVAILABLE_MESSAGE}
    # The user's message was persisted before the unavailable run was attempted.
    assert store.writes == [(USER_ID, CONVERSATION_ID, "Hello")]
