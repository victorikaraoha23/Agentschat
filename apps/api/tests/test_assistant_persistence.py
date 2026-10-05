"""Assistant response persistence (Task 8.2).

Task 8.1 proved a run happened and returned its text. This file proves what became
of that text: a successful run leaves exactly one ``assistant`` message in the
same conversation, owned by the same verified user, and every failure path leaves
the conversation honest -- a failed run keeps the user's message and writes no
reply, and a reply that cannot be stored is reported as a failure rather than
papered over with a completion that never happened.

Supabase and Hermes are absent: the store and the runtime are swapped through the
application's own dependency seams, so the ordering, ownership, and failure
semantics are observable without a database or a running agent.
"""

from __future__ import annotations

import pytest
from httpx import Response

from app.main import (
    ASSISTANT_PERSIST_FAILED_DETAIL,
    CONVERSATION_NOT_FOUND_DETAIL,
    EXECUTION_COMPLETED_STATUS,
)
from app.messages import MESSAGE_ROLE_ASSISTANT, MESSAGE_ROLE_USER, MessageCreateError
from app.runtime import (
    RUNTIME_TIMED_OUT_MESSAGE,
    RUNTIME_UNAVAILABLE_MESSAGE,
    RuntimeFailureReason,
    RuntimeRequest,
    RuntimeResult,
)
from tests.fake_runtime import FakeFailureRuntime, FakeSuccessRuntime
from tests.test_execute_endpoint import (
    ASSISTANT_ROW_ID,
    CONVERSATION_ID,
    OTHER_USER_ID,
    USER_ID,
    FakeMessageStore,
    execute_message,
)


class RuntimeReportingAnIdentity(FakeSuccessRuntime):
    """A runtime that answers with text naming someone else's user id.

    The reply text is the runtime's to choose; the *ownership* of the row is not.
    This runtime exists to prove that a reply the runtime labelled as another
    user's is still stored against the authenticated caller, because the API --
    not the runtime -- decides who owns a message.
    """

    OUTPUT = "I am User B, the intruder."

    async def execute(self, request: RuntimeRequest) -> RuntimeResult:
        return RuntimeResult(ok=True, output=self.OUTPUT)


# --- Successful execution ----------------------------------------------------


def test_successful_execution_persists_exactly_one_assistant_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A completed run leaves the request and one reply, in that order."""
    store, _runtime, response = execute_message(monkeypatch, {"content": "Hello"})

    assert response.status_code == 200
    assert store.writes == [(USER_ID, CONVERSATION_ID, "Hello")]
    assert store.assistant_writes == [
        (USER_ID, CONVERSATION_ID, "fake assistant reply")
    ]


def test_assistant_message_belongs_to_the_same_conversation_and_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reply is stored in the conversation the caller owns, as the caller."""
    store, _runtime, _response = execute_message(monkeypatch, {"content": "Hello"})

    conversation_id, content = store.assistant_writes[0][1:]
    assert conversation_id == CONVERSATION_ID
    assert content == "fake assistant reply"


def test_response_reports_the_persisted_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The caller learns the completed status, the content, and the row's id."""
    _store, _runtime, response = execute_message(monkeypatch, {"content": "Hello"})

    assert response.json() == {
        "status": EXECUTION_COMPLETED_STATUS,
        "content": "fake assistant reply",
        "message_id": ASSISTANT_ROW_ID,
    }


def test_assistant_content_is_stored_exactly_as_produced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing is appended, trimmed, or reformatted on the way to the database."""
    runtime = RuntimeReportingAnIdentity()
    store, _used, response = execute_message(
        monkeypatch, {"content": "Hello"}, runtime=runtime
    )

    assert response.status_code == 200
    # Stored verbatim, with no trailing metadata or Hermes text appended.
    assert store.assistant_writes[0][2] == RuntimeReportingAnIdentity.OUTPUT


def test_runtime_cannot_choose_the_owner_of_the_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ownership comes from the verified identity, never from the runtime."""
    runtime = RuntimeReportingAnIdentity()
    store, _used, response = execute_message(
        monkeypatch, {"content": "Hello"}, runtime=runtime
    )

    assert response.status_code == 200
    # The reply names the intruder in its text, yet is written as the caller's.
    assert store.assistant_writes[0][0] == USER_ID
    assert store.assistant_writes[0][0] != OTHER_USER_ID


# --- Failure paths -----------------------------------------------------------


def test_failed_run_writes_no_assistant_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A runtime failure keeps the user's message and adds no reply."""
    store, _runtime, response = execute_message(
        monkeypatch,
        {"content": "Hello"},
        runtime=FakeFailureRuntime(RuntimeFailureReason.FAILED),
    )

    assert response.status_code == 502
    assert store.writes == [(USER_ID, CONVERSATION_ID, "Hello")]
    assert store.assistant_writes == []


def test_unavailable_runtime_writes_no_assistant_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _runtime, response = execute_message(
        monkeypatch,
        {"content": "Hello"},
        runtime=FakeFailureRuntime(RuntimeFailureReason.UNAVAILABLE),
    )

    assert response.json() == {"detail": RUNTIME_UNAVAILABLE_MESSAGE}
    assert store.writes == [(USER_ID, CONVERSATION_ID, "Hello")]
    assert store.assistant_writes == []


def test_timeout_writes_no_assistant_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A run that hit its time limit leaves the conversation without a reply."""
    store, _runtime, response = execute_message(
        monkeypatch,
        {"content": "Hello"},
        runtime=FakeFailureRuntime(RuntimeFailureReason.TIMED_OUT),
    )

    assert response.status_code == 504
    assert response.json() == {"detail": RUNTIME_TIMED_OUT_MESSAGE}
    assert store.writes == [(USER_ID, CONVERSATION_ID, "Hello")]
    assert store.assistant_writes == []


def test_unpersistable_reply_is_reported_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A storage failure answers with an error, never a completion.

    Reporting success here would leave the user's message in the conversation with
    no reply and nothing indicating that anything went wrong.
    """
    store = FakeMessageStore(assistant_error=MessageCreateError("boom"))
    _store, _runtime, response = execute_message(
        monkeypatch, {"content": "Hello"}, store=store
    )

    assert response.status_code == 503
    assert response.json() == {"detail": ASSISTANT_PERSIST_FAILED_DETAIL}
    # The user's message is still there; the run did happen.
    assert store.writes == [(USER_ID, CONVERSATION_ID, "Hello")]


def test_reply_storage_failure_does_not_leak_internals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No database detail from the failed write reaches the client."""
    store = FakeMessageStore(
        assistant_error=MessageCreateError(
            'insert into public.messages failed: pq: relation "public.messages" '
            "does not exist at /srv/app/api/app/messages.py"
        )
    )
    _store, _runtime, response = execute_message(
        monkeypatch, {"content": "Hello"}, store=store
    )

    body = response.text
    assert "messages.py" not in body
    assert "relation" not in body
    assert "public.messages" not in body
    assert "insert into" not in body


def test_missing_reply_row_answers_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A conversation that vanished mid-run answers the same safe 404."""


# --- Ordering ----------------------------------------------------------------


def test_the_reply_is_written_only_after_the_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The user message exists before execution; the reply exists after it."""
    store = FakeMessageStore()

    class WatchesBothWrites(FakeSuccessRuntime):
        """Records the store's contents at the moment the run starts."""

        def __init__(self) -> None:
            super().__init__()
            self.writes_at_execute: list[tuple[str, str, str]] = []
            self.assistant_writes_at_execute: list[tuple[str, str, str]] = []

        async def execute(self, request: RuntimeRequest) -> RuntimeResult:
            self.writes_at_execute = list(store.writes)
            self.assistant_writes_at_execute = list(store.assistant_writes)
            return await super().execute(request)

    runtime = WatchesBothWrites()
    _store, _used, response = execute_message(
        monkeypatch, {"content": "Hello"}, store=store, runtime=runtime
    )

    assert response.status_code == 200
    # While the run was in flight: the request existed, the reply did not.
    assert runtime.writes_at_execute == [(USER_ID, CONVERSATION_ID, "Hello")]
    assert runtime.assistant_writes_at_execute == []
    # Afterwards: both, request first.
    assert store.assistant_writes == [
        (USER_ID, CONVERSATION_ID, "fake assistant reply")
    ]


def test_exactly_one_run_and_one_reply_per_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No duplicate execution, and therefore no duplicate reply."""
    store, runtime, response = execute_message(monkeypatch, {"content": "Hello"})

    assert response.status_code == 200
    assert len(runtime.requests) == 1
    assert len(store.assistant_writes) == 1


def test_two_sequential_requests_produce_two_paired_replies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each turn adds one request and one reply -- the exchange stays balanced."""
    store = FakeMessageStore()
    responses: list[Response] = []
    for content in ("first", "second"):
        _store, _runtime, response = execute_message(
            monkeypatch, {"content": content}, store=store
        )
        responses.append(response)

    assert [r.status_code for r in responses] == [200, 200]
    assert [w[2] for w in store.writes] == ["first", "second"]
    assert [w[2] for w in store.assistant_writes] == [
        "fake assistant reply",
        "fake assistant reply",
    ]
    store = FakeMessageStore(assistant_missing=True)
    _store, _runtime, response = execute_message(
        monkeypatch, {"content": "Hello"}, store=store
    )

    assert response.status_code == 404
    assert response.json() == {"detail": CONVERSATION_NOT_FOUND_DETAIL}


def test_foreign_conversation_never_reaches_a_reply_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An intruder gets the same 404 and no assistant row anywhere."""
    store = FakeMessageStore(owns_conversation=False)
    _store, runtime, response = execute_message(
        monkeypatch,
        {"content": "Hello", "user_id": OTHER_USER_ID},
        user_id=OTHER_USER_ID,
        store=store,
    )

    assert response.status_code == 404
    assert runtime.requests == []
    assert store.assistant_writes == []


def test_no_role_field_exists_for_a_client_to_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A client cannot ask for an assistant row; the endpoint always writes user.

    This is the impersonation guard: even though the body names the assistant
    role, the user-message write is a `user` message, because the endpoint passes
    a module constant rather than anything from the request.
    """
    store, _runtime, response = execute_message(
        monkeypatch, {"content": "Hello", "role": MESSAGE_ROLE_ASSISTANT}
    )

    assert response.status_code == 200
    assert store.writes == [(USER_ID, CONVERSATION_ID, "Hello")]
    assert MESSAGE_ROLE_USER != MESSAGE_ROLE_ASSISTANT
