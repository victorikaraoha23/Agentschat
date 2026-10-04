"""Message creation: POST /conversations/{conversation_id}/messages (Task 6.2).

The store is faked through the module's seams, so no test needs a live Supabase
project or credentials. Ownership always comes from the verified identity the
Task 3.2 dependency resolves -- never from request data -- and a conversation the
caller does not own is answered exactly like one that does not exist.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.auth import AuthenticatedUser, get_access_token_verifier
from app.main import MAX_MESSAGE_CONTENT_LENGTH, app, get_message_store
from app.messages import Message, MessageCreateError

USER_ID = "123e4567-e89b-12d3-a456-426614174000"
OTHER_USER_ID = "123e4567-e89b-12d3-a456-426614174999"
CONVERSATION_ID = "223e4567-e89b-12d3-a456-426614174000"

CREATED_ROW: dict[str, object] = {
    "id": "323e4567-e89b-12d3-a456-426614174000",
    "conversation_id": CONVERSATION_ID,
    "user_id": USER_ID,
    "role": "user",
    "content": "Hello",
    "created_at": "2026-10-04T12:00:00Z",
}


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
    """Stand-in for the message store: records writes, replays a row."""

    def __init__(
        self,
        owns_conversation: bool = True,
        error: Exception | None = None,
    ) -> None:
        """Decide whether the caller owns the conversation, or raise an error."""
        self._owns_conversation = owns_conversation
        self._error = error
        self.writes: list[tuple[str, str, str]] = []

    def create_for_user(
        self, user_id: str, conversation_id: str, content: str
    ) -> Message | None:
        """Record the write; answer `None` for a conversation the caller lacks."""
        self.writes.append((user_id, conversation_id, content))
        if self._error is not None:
            raise self._error
        if not self._owns_conversation:
            return None
        return Message.model_validate(
            {
                **CREATED_ROW,
                "conversation_id": conversation_id,
                "user_id": user_id,
                "content": content,
            }
        )


def post_message(
    monkeypatch: pytest.MonkeyPatch,
    body: object,
    user_id: str = USER_ID,
    store: FakeMessageStore | None = None,
    conversation_id: str = CONVERSATION_ID,
) -> tuple[FakeMessageStore, Any]:
    """POST a message with faked auth and store; return the store and response."""
    active = store if store is not None else FakeMessageStore()
    monkeypatch.setitem(
        app.dependency_overrides,
        get_access_token_verifier,
        lambda: FakeVerifier(user_id),
    )
    monkeypatch.setitem(app.dependency_overrides, get_message_store, lambda: active)
    try:
        response = TestClient(app, raise_server_exceptions=False).post(
            f"/conversations/{conversation_id}/messages",
            json=body,
            headers={"Authorization": "Bearer header.payload.signature"},
        )
    finally:
        app.dependency_overrides = {}
    return active, response

def test_unauthenticated_message_is_rejected() -> None:
    """No bearer token means the 401 authentication error, never a row."""
    response = TestClient(app).post(
        f"/conversations/{CONVERSATION_ID}/messages", json={"content": "Hello"}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


def test_owner_sends_a_message_and_receives_the_persisted_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid message is stored with the caller's identity and returned as 201."""
    store, response = post_message(monkeypatch, {"content": "Hello"})

    assert response.status_code == 201
    assert response.json() == {
        "id": "323e4567-e89b-12d3-a456-426614174000",
        "conversation_id": CONVERSATION_ID,
        "user_id": USER_ID,
        "role": "user",
        "content": "Hello",
        "created_at": "2026-10-04T12:00:00Z",
    }
    assert store.writes == [(USER_ID, CONVERSATION_ID, "Hello")]


def test_message_is_written_to_the_conversation_in_the_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The conversation comes from the route, never from the body."""
    other_conversation = "423e4567-e89b-12d3-a456-426614174000"
    store, response = post_message(
        monkeypatch,
        {"content": "Hello", "conversation_id": "623e4567-e89b-12d3-a456-426614174000"},
        conversation_id=other_conversation,
    )

    assert response.status_code == 201
    assert response.json()["conversation_id"] == other_conversation
    assert store.writes == [(USER_ID, other_conversation, "Hello")]


def test_forged_user_id_in_body_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    """A body `user_id` naming someone else is dropped; the author is the caller."""
    store, response = post_message(
        monkeypatch, {"content": "Hello", "user_id": OTHER_USER_ID}
    )

    assert response.status_code == 201
    assert response.json()["user_id"] == USER_ID
    assert store.writes == [(USER_ID, CONVERSATION_ID, "Hello")]


def test_role_is_always_user(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only the user role is produced; a body cannot choose another role."""
    _store, response = post_message(monkeypatch, {"content": "Hello", "role": "assistant"})

    assert response.status_code == 201
    assert response.json()["role"] == "user"


def test_content_is_trimmed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Surrounding whitespace is removed before the message is stored."""
    store, response = post_message(monkeypatch, {"content": "  Hello  "})

    assert response.status_code == 201
    assert store.writes == [(USER_ID, CONVERSATION_ID, "Hello")]


def test_missing_content_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A body without content is a 422 and writes nothing."""
    store, response = post_message(monkeypatch, {})

    assert response.status_code == 422
    assert store.writes == []


def test_empty_content_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty string is a validation error, not a blank message."""
    store, response = post_message(monkeypatch, {"content": ""})

    assert response.status_code == 422
    assert store.writes == []


@pytest.mark.parametrize("content", ["   ", "\n", "\t  \n"])
def test_whitespace_only_content_is_rejected(
    monkeypatch: pytest.MonkeyPatch, content: str
) -> None:
    """Whitespace-only content carries no message and is never stored."""
    store, response = post_message(monkeypatch, {"content": content})

    assert response.status_code == 422
    assert store.writes == []


def test_overlong_content_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Content past the documented limit is a 422 and writes nothing."""
    store, response = post_message(
        monkeypatch, {"content": "x" * (MAX_MESSAGE_CONTENT_LENGTH + 1)}
    )

    assert response.status_code == 422
    assert store.writes == []


def test_content_at_the_limit_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """The limit itself is valid input."""
    _store, response = post_message(monkeypatch, {"content": "x" * MAX_MESSAGE_CONTENT_LENGTH})

    assert response.status_code == 201


def test_wrong_content_type_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-string content is refused by the model layer."""
    store, response = post_message(monkeypatch, {"content": {"text": "Hello"}})

    assert response.status_code == 422
    assert store.writes == []


def test_message_with_invalid_path_id_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A malformed conversation id is refused before any query runs."""
    store, response = post_message(
        monkeypatch, {"content": "Hello"}, conversation_id="not-a-uuid"
    )

    assert response.status_code == 422
    assert store.writes == []

def test_user_cannot_write_into_another_users_conversation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A conversation the caller does not own is a 404 and writes nothing."""
    store, response = post_message(
        monkeypatch, {"content": "Hello"}, store=FakeMessageStore(owns_conversation=False)
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Conversation not found."}
    assert store.writes == [(USER_ID, CONVERSATION_ID, "Hello")]


def test_each_user_writes_only_into_their_own_conversation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two users, two conversations: neither write crosses the boundary."""
    owner = FakeMessageStore()
    post_message(monkeypatch, {"content": "Mine"}, user_id=USER_ID, store=owner)

    intruder = FakeMessageStore(owns_conversation=False)
    _store, response = post_message(
        monkeypatch, {"content": "Theirs"}, user_id=OTHER_USER_ID, store=intruder
    )

    assert owner.writes == [(USER_ID, CONVERSATION_ID, "Mine")]
    assert intruder.writes == [(OTHER_USER_ID, CONVERSATION_ID, "Theirs")]
    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found."


def test_missing_and_foreign_conversations_answer_identically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A foreign conversation and a nonexistent one are the same observation."""
    _foreign, foreign = post_message(
        monkeypatch, {"content": "Hello"}, store=FakeMessageStore(owns_conversation=False)
    )
    _missing, missing = post_message(
        monkeypatch, {"content": "Hello"}, store=FakeMessageStore(owns_conversation=False)
    )

    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()


def test_failing_store_is_a_safe_503(monkeypatch: pytest.MonkeyPatch) -> None:
    """A store failure answers the fixed detail, with no internals attached."""
    _store, response = post_message(
        monkeypatch, {"content": "Hello"}, store=FakeMessageStore(error=MessageCreateError())
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "The message could not be sent."}


def test_broken_created_row_is_a_safe_500(monkeypatch: pytest.MonkeyPatch) -> None:
    """A row the store cannot parse becomes the generic server error."""

    class BrokenRowStore(FakeMessageStore):
        """Return a row whose id is not a UUID, so parsing fails as it would live."""

        def create_for_user(
            self, user_id: str, conversation_id: str, content: str
        ) -> Message:
            """Validate a malformed row, exactly as the real store does."""
            self.writes.append((user_id, conversation_id, content))
            return Message.model_validate({**CREATED_ROW, "id": "not-a-uuid"})

    _store, response = post_message(monkeypatch, {"content": "Hello"}, store=BrokenRowStore())

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error."}