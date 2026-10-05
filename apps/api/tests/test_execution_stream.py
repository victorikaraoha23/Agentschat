"""Streamed execution: POST /conversations/{conversation_id}/execute/stream.

Task 8.3 streams the reply instead of waiting for it, so the questions here are
about a response that begins before the answer is known: does authentication and
ownership still fail *before* the stream opens, is the user's message still stored
first, does each delta reach the client in order, and -- the one that matters most
-- does a run that failed half way leave no assistant message behind.

The stream is read here as the raw bytes a browser would receive, so the SSE
framing itself is under test rather than just the calls behind it. No Hermes, no
model, no database: the runtime and the store are swapped through the
application's own dependency seams.
"""

from __future__ import annotations

import asyncio
import json
from uuid import UUID
from collections.abc import AsyncIterator

import pytest
from anyio import CancelScope
from starlette.types import Message as ASGIMessage
from fastapi.testclient import TestClient

from app.auth import get_access_token_verifier
from app.main import (
    ASSISTANT_PERSIST_FAILED_DETAIL,
    CONVERSATION_NOT_FOUND_DETAIL,
    MAX_MESSAGE_CONTENT_LENGTH,
    app,
    get_message_store,
)
from app.messages import Message, MessageCreateError
from app.runtime import (
    RUNTIME_FAILED_MESSAGE,
    RUNTIME_TIMED_OUT_MESSAGE,
    RUNTIME_UNAVAILABLE_MESSAGE,
    RuntimeFailureReason,
    RuntimeRequest,
    RuntimeStreamEvent,
    RuntimeStreamEventKind,
    get_agent_runtime,
)
from tests.fake_runtime import (
    FakeFailureRuntime,
    FakeSuccessRuntime,
    PartialThenFailRuntime,
)
from tests.test_execute_endpoint import (
    ASSISTANT_ROW_ID,
    CONVERSATION_ID,
    CREATED_ROW,
    OTHER_USER_ID,
    USER_ID,
    FakeMessageStore,
    FakeVerifier,
)

client = TestClient(app)


def stream_events(response_text: str) -> list[tuple[str, dict[str, object]]]:
    """Parse a whole SSE body into its `(event, data)` pairs.

    The parser is deliberately simple because the server's framing is fixed: each
    event is one `event:` line and one JSON `data:` line, separated by a blank
    line. Anything unreadable is skipped rather than failing the test silently --
    an unexpected body shows up as a missing expected event.
    """
    events: list[tuple[str, dict[str, object]]] = []
    for block in response_text.split("\n\n"):
        name = ""
        payload = ""
        for line in block.splitlines():
            if line.startswith("event:"):
                name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                payload = line[len("data:") :].strip()
        if not name or not payload:
            continue
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, dict):
            events.append((name, decoded))
    return events


def event_names(response_text: str) -> list[str]:
    return [name for name, _ in stream_events(response_text)]


def deltas(response_text: str) -> list[str]:
    return [
        str(data["content"])
        for name, data in stream_events(response_text)
        if name == "delta"
    ]


def post_stream(
    monkeypatch: pytest.MonkeyPatch,
    body: object,
    *,
    runtime: object | None = None,
    store: FakeMessageStore | None = None,
    user_id: str = USER_ID,
    conversation_id: str = CONVERSATION_ID,
    authenticated: bool = True,
):
    """POST to the streaming endpoint with faked auth, store, and runtime."""
    active_store = store if store is not None else FakeMessageStore()
    active_runtime = runtime if runtime is not None else FakeSuccessRuntime()
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
    path = f"/conversations/{conversation_id}/execute/stream"
    headers = (
        {"Authorization": "Bearer header.payload.signature"} if authenticated else None
    )
    return (
        active_store,
        active_runtime,
        client.post(path, json=body, headers=headers),
    )


class NewlineRuntime(FakeSuccessRuntime):
    """A reply containing newlines, which must not split into extra events."""

    async def stream(
        self, request: RuntimeRequest
    ) -> AsyncIterator[RuntimeStreamEvent]:
        self.requests.append(request)
        text = "line one\nline two\n"
        yield RuntimeStreamEvent(kind=RuntimeStreamEventKind.DELTA, content=text)
        yield RuntimeStreamEvent(kind=RuntimeStreamEventKind.COMPLETED, content=text)


# --- Failure during streaming ------------------------------------------------


def test_a_failed_run_emits_an_error_and_no_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeMessageStore()
    _s, _r, response = post_stream(
        monkeypatch,
        {"content": "Hello"},
        runtime=FakeFailureRuntime(RuntimeFailureReason.FAILED),
        store=store,
    )

    events = stream_events(response.text)
    assert [name for name, _ in events] == ["start", "error"]
    assert events[-1][1] == {"code": "failed", "message": RUNTIME_FAILED_MESSAGE}


@pytest.mark.parametrize(
    ("reason", "message"),
    [
        (RuntimeFailureReason.UNAVAILABLE, RUNTIME_UNAVAILABLE_MESSAGE),
        (RuntimeFailureReason.TIMED_OUT, RUNTIME_TIMED_OUT_MESSAGE),
        (RuntimeFailureReason.FAILED, RUNTIME_FAILED_MESSAGE),
    ],
)
def test_every_runtime_failure_maps_to_its_fixed_wording(
    monkeypatch: pytest.MonkeyPatch,
    reason: RuntimeFailureReason,
    message: str,
) -> None:
    _store, _runtime, response = post_stream(
        monkeypatch,
        {"content": "Hello"},
        runtime=FakeFailureRuntime(reason),
    )

    errors = [data for name, data in stream_events(response.text) if name == "error"]
    assert errors == [{"code": reason.value, "message": message}]


def test_a_failed_run_writes_no_assistant_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeMessageStore()
    _s, _r, response = post_stream(
        monkeypatch,
        {"content": "Hello"},
        runtime=FakeFailureRuntime(RuntimeFailureReason.FAILED),
        store=store,
    )

    assert response.status_code == 200
    # The user's request stays; no reply is invented.
    assert store.writes == [(USER_ID, CONVERSATION_ID, "Hello")]
    assert store.assistant_writes == []


def test_a_timed_out_run_writes_no_assistant_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeMessageStore()
    _s, _r, response = post_stream(
        monkeypatch,
        {"content": "Hello"},
        runtime=FakeFailureRuntime(RuntimeFailureReason.TIMED_OUT),
        store=store,
    )

    assert "error" in event_names(response.text)
    assert store.writes == [(USER_ID, CONVERSATION_ID, "Hello")]
    assert store.assistant_writes == []


def test_partial_output_is_shown_but_never_stored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Text produced before a failure is streamed, and then discarded.

    The client may show it while the stream is open, but the conversation must not
    gain a message that the agent never finished producing.
    """
    store = FakeMessageStore()
    partial = PartialThenFailRuntime()
    _s, _r, response = post_stream(
        monkeypatch, {"content": "Hello"}, runtime=partial, store=store
    )

    assert deltas(response.text) == [partial.partial]
    assert event_names(response.text) == ["start", "delta", "error"]
    assert store.writes == [(USER_ID, CONVERSATION_ID, "Hello")]
    assert store.assistant_writes == []


def test_an_unstorable_reply_is_an_error_not_a_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeMessageStore(assistant_error=MessageCreateError("boom"))
    _s, _r, response = post_stream(monkeypatch, {"content": "Hello"}, store=store)

    events = stream_events(response.text)
    assert [name for name, _ in events][-1] == "error"
    assert "complete" not in event_names(response.text)
    assert events[-1][1] == {
        "code": "assistant-persist-failed",
        "message": ASSISTANT_PERSIST_FAILED_DETAIL,
    }


def test_storage_failure_details_never_reach_the_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeMessageStore(
        assistant_error=MessageCreateError(
            "insert into public.messages failed at /srv/app/api/app/messages.py"
        )
    )
    _s, _r, response = post_stream(monkeypatch, {"content": "Hello"}, store=store)

    assert "messages.py" not in response.text
    assert "insert into" not in response.text


def test_a_vanished_conversation_is_reported_as_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeMessageStore(assistant_missing=True)
    _s, _r, response = post_stream(monkeypatch, {"content": "Hello"}, store=store)

    errors = [data for name, data in stream_events(response.text) if name == "error"]
    assert errors == [{"code": "not-found", "message": CONVERSATION_NOT_FOUND_DETAIL}]
    """Content is JSON-encoded, so a newline cannot split one event into two."""
    _store, _runtime, response = post_stream(
        monkeypatch, {"content": "Hello"}, runtime=NewlineRuntime()
    )

    assert deltas(response.text) == ["line one\nline two\n"]
    assert event_names(response.text) == ["start", "delta", "complete"]


def test_the_stream_path_is_separate_from_the_buffered_one() -> None:
    """The buffered endpoint keeps answering JSON; streaming adds, not replaces."""
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/conversations/{conversation_id}/execute" in paths
    assert "/conversations/{conversation_id}/execute/stream" in paths


# --- Before the stream opens -------------------------------------------------


def test_the_response_is_an_event_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    _store, _runtime, response = post_stream(monkeypatch, {"content": "Hello"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")


def test_a_buffering_proxy_is_told_not_to_buffer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without this header a proxy would hold the whole reply before sending it."""
    _store, _runtime, response = post_stream(monkeypatch, {"content": "Hello"})

    assert response.headers["x-accel-buffering"] == "no"
    assert response.headers["cache-control"] == "no-cache"


def test_an_unauthenticated_request_is_rejected_before_streaming(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, runtime, response = post_stream(
        monkeypatch, {"content": "Hello"}, authenticated=False
    )

    assert response.status_code == 401
    assert store.writes == []
    assert runtime.requests == []


def test_a_foreign_conversation_is_a_404_before_streaming(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeMessageStore(owns_conversation=False)
    _store, runtime, response = post_stream(
        monkeypatch,
        {"content": "Hello"},
        store=store,
        user_id=OTHER_USER_ID,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": CONVERSATION_NOT_FOUND_DETAIL}
    assert runtime.requests == []
    assert store.assistant_writes == []


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"content": ""},
        {"content": "   "},
        {"content": "x" * (MAX_MESSAGE_CONTENT_LENGTH + 1)},
    ],
)
def test_invalid_content_is_a_422_before_streaming(
    monkeypatch: pytest.MonkeyPatch, body: dict[str, object]
) -> None:
    store, runtime, response = post_stream(monkeypatch, body)

    assert response.status_code == 422
    assert store.writes == []
    assert runtime.requests == []


def test_the_user_message_is_persisted_before_the_stream_opens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, runtime, response = post_stream(monkeypatch, {"content": "Hello"})

    assert response.status_code == 200
    assert store.writes == [(USER_ID, CONVERSATION_ID, "Hello")]
    assert len(runtime.requests) == 1


# --- Streaming the reply -----------------------------------------------------


def test_deltas_are_emitted_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    _store, _runtime, response = post_stream(monkeypatch, {"content": "Hello"})

    # The fake splits the answer in half, so two deltas must arrive in that order.
    emitted = deltas(response.text)
    assert len(emitted) == 2
    assert "".join(emitted) == "fake assistant reply"


def test_the_complete_event_carries_the_persisted_message_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _runtime, response = post_stream(monkeypatch, {"content": "Hello"})

    completes = [
        data for name, data in stream_events(response.text) if name == "complete"
    ]
    assert len(completes) == 1
    assert completes[0]["message_id"] == ASSISTANT_ROW_ID
    assert completes[0]["content"] == "fake assistant reply"
    assert completes[0]["message"]["user_id"] == USER_ID
    assert completes[0]["message"]["created_at"] == CREATED_ROW["created_at"]


def test_the_reply_is_persisted_once_after_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _runtime, response = post_stream(monkeypatch, {"content": "Hello"})

    assert response.status_code == 200
    assert store.assistant_writes == [
        (USER_ID, CONVERSATION_ID, "fake assistant reply")
    ]


def test_exactly_one_run_occurs_per_request(monkeypatch: pytest.MonkeyPatch) -> None:
    _store, runtime, response = post_stream(monkeypatch, {"content": "Hello"})

    assert response.status_code == 200
    assert len(runtime.requests) == 1


def test_no_hermes_event_vocabulary_reaches_the_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only application event names may appear in the body."""
    _store, _runtime, response = post_stream(monkeypatch, {"content": "Hello"})

    assert set(event_names(response.text)) <= {"start", "delta", "complete", "error"}
    for word in ("tool_use", "tool_result", "session_id", "tokens", "exit_code"):
        assert word not in response.text


def test_a_delta_containing_newlines_stays_one_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Content is JSON-encoded, so a newline cannot split one event into two."""
    _store, _runtime, response = post_stream(
        monkeypatch, {"content": "Hello"}, runtime=NewlineRuntime()
    )

    assert deltas(response.text) == ["line one\nline two\n"]
    assert event_names(response.text) == ["start", "delta", "complete"]


@pytest.mark.parametrize("raises", [False, True])
def test_missing_terminal_or_exception_produces_one_safe_error(
    monkeypatch: pytest.MonkeyPatch, raises: bool,
) -> None:
    class BrokenRuntime(FakeSuccessRuntime):
        async def stream(self, request: RuntimeRequest) -> AsyncIterator[RuntimeStreamEvent]:
            yield RuntimeStreamEvent(kind=RuntimeStreamEventKind.DELTA, content="partial")
            if raises:
                raise RuntimeError("private runtime detail")

    store, _, response = post_stream(monkeypatch, {"content": "Hello"}, runtime=BrokenRuntime())
    assert event_names(response.text) == ["start", "delta", "error"]
    assert stream_events(response.text)[-1][1] == {
        "code": "failed", "message": RUNTIME_FAILED_MESSAGE,
    }
    assert "private runtime detail" not in response.text
    assert not store.assistant_writes


def test_start_and_completion_carry_persisted_rows_after_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order: list[str] = []

    class ClosingRuntime(FakeSuccessRuntime):
        async def stream(self, request: RuntimeRequest) -> AsyncIterator[RuntimeStreamEvent]:
            try:
                yield RuntimeStreamEvent(kind=RuntimeStreamEventKind.DELTA, content="draft")
                yield RuntimeStreamEvent(kind=RuntimeStreamEventKind.COMPLETED, content="final")
                raise AssertionError("must stop at the first terminal event")
            finally:
                await asyncio.sleep(0)
                order.append("closed")

    class CanonicalStore(FakeMessageStore):
        def create_assistant_for_user(
            self, user_id: str, conversation_id: str, content: str,
        ) -> Message | None:
            assert order == ["closed"]
            order.append("persisted")
            row = super().create_assistant_for_user(user_id, conversation_id, content)
            assert row is not None
            return row.model_copy(update={"content": "stored final"})

    store, _, response = post_stream(
        monkeypatch, {"content": "Hello"}, store=CanonicalStore(), runtime=ClosingRuntime(),
    )
    events = stream_events(response.text)
    assert events[0] == ("start", {"message": Message.model_validate({
        **CREATED_ROW, "content": "Hello",
    }).model_dump(mode="json")})
    assert events[-1][0] == "complete"
    assert events[-1][1]["content"] == "stored final"
    assert events[-1][1]["message"]["content"] == "stored final"
    assert order == ["closed", "persisted"]
    assert store.assistant_writes == [(USER_ID, CONVERSATION_ID, "final")]


@pytest.mark.parametrize("spec_version", ["2.0", "2.4"])
@pytest.mark.parametrize("during_read", [False, True])
def test_disconnect_closes_response_and_runtime_before_returning(
    spec_version: str, during_read: bool,
) -> None:
    from app.main import ExecutionStreamingResponse, _stream_execution_events
    from starlette.requests import ClientDisconnect

    async def run() -> None:
        closed = False
        ready = asyncio.Event()
        store = FakeMessageStore()

        class WaitingRuntime(FakeSuccessRuntime):
            async def stream(self, request: RuntimeRequest) -> AsyncIterator[RuntimeStreamEvent]:
                nonlocal closed
                try:
                    yield RuntimeStreamEvent(kind=RuntimeStreamEventKind.DELTA, content="partial")
                    ready.set()
                    await asyncio.Event().wait()
                finally:
                    # Runtime implementations shield their resource teardown.
                    with CancelScope(shield=True):
                        await asyncio.sleep(0)
                        closed = True

        request = RuntimeRequest(
            user_id=UUID(USER_ID), conversation_id=UUID(CONVERSATION_ID), content="Hello",
        )
        body = _stream_execution_events(
            UUID(CONVERSATION_ID), request, USER_ID, store, WaitingRuntime(),
            Message.model_validate(CREATED_ROW),
        )
        response = ExecutionStreamingResponse(body)

        async def send(message: ASGIMessage) -> None:
            if message["type"] == "http.response.body" and b"event: delta" in message["body"]:
                if not during_read:
                    ready.set()
                    if spec_version == "2.4":
                        raise OSError("client disconnected")
                    await asyncio.Event().wait()

        async def receive() -> ASGIMessage:
            await ready.wait()
            return {"type": "http.disconnect"}

        task = asyncio.create_task(response(
            {"type": "http", "asgi": {"spec_version": spec_version}}, receive, send,
        ))
        if spec_version == "2.4" and during_read:
            await ready.wait()
            task.cancel()
        try:
            await asyncio.wait_for(task, 2)
        except (ClientDisconnect, asyncio.CancelledError):
            assert spec_version == "2.4"
        assert closed
        assert body.ag_frame is None
        assert store.assistant_writes == []

    asyncio.run(run())
