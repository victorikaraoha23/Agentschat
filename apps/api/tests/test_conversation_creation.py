"""Conversation creation: POST /conversations (Task 5.2).

The store is faked through the module's seams, so no test needs a live
Supabase project or credentials. Ownership always comes from the verified
identity the Task 3.2 dependency resolves — never from request data.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth import AuthenticatedUser, get_access_token_verifier
from app.config import Settings
from app.conversations import (
    ConversationCreateError,
    SupabaseConversationStore,
)
from app.main import MAX_CONVERSATION_TITLE_LENGTH, app, get_conversation_store

USER_ID = "123e4567-e89b-12d3-a456-426614174000"
OTHER_USER_ID = "123e4567-e89b-12d3-a456-426614174999"

CREATED_ROW = {
    "id": "223e4567-e89b-12d3-a456-426614174000",
    "user_id": USER_ID,
    "title": None,
    "created_at": "2026-10-04T12:00:00Z",
    "updated_at": "2026-10-04T12:00:00Z",
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


class FakeStore:
    """Stand-in for the conversation store: records writes, replays a row."""

    def __init__(
        self,
        row: dict[str, object] | None = CREATED_ROW,
        error: Exception | None = None,
    ) -> None:
        """Prepare the row to return (or the error to raise) on create."""
        self._row = dict(row) if row is not None else None
        self._error = error
        self.writes: list[tuple[str, object]] = []

    def create(self, user_id: str, title: str | None):  # type: ignore[no-untyped-def]
        """Record the write and return the prepared row for the owner."""
        from app.conversations import Conversation

        self.writes.append((user_id, title))
        if self._error is not None:
            raise self._error
        assert self._row is not None
        row = dict(self._row)
        row["user_id"] = user_id
        row["title"] = title
        return Conversation.model_validate(row)


def post_conversation(
    monkeypatch: pytest.MonkeyPatch,
    body: object,
    user_id: str = USER_ID,
    store: FakeStore | None = None,
) -> tuple[TestClient, object]:
    """POST /conversations with faked auth and store; return client + response."""
    active = store if store is not None else FakeStore()
    monkeypatch.setitem(
        app.dependency_overrides,
        get_access_token_verifier,
        lambda: FakeVerifier(user_id),
    )
    monkeypatch.setitem(app.dependency_overrides, get_conversation_store, lambda: active)
    try:
        response = TestClient(app, raise_server_exceptions=False).post(
            "/conversations",
            json=body,
            headers={"Authorization": "Bearer header.payload.signature"},
        )
    finally:
        app.dependency_overrides = {}
    return active, response


def test_unauthenticated_create_is_rejected() -> None:
    """No bearer token means the 401 authentication error, never a row."""
    response = TestClient(app).post("/conversations", json={})

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


def test_create_without_title_persists_null_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Omitting the title stores NULL and returns 201 with the created row."""
    store, response = post_conversation(monkeypatch, {})

    assert response.status_code == 201
    assert response.json() == CREATED_ROW
    assert store.writes == [(USER_ID, None)]


def test_create_with_valid_title_trims_surrounding_whitespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Surrounding whitespace is trimmed before the row is written."""
    store, response = post_conversation(monkeypatch, {"title": "  hello  "})

    assert response.status_code == 201
    assert response.json()["title"] == "hello"
    assert store.writes == [(USER_ID, "hello")]


def test_create_with_blank_title_stores_null(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Whitespace-only titles become NULL rather than empty strings."""
    store, response = post_conversation(monkeypatch, {"title": "   "})

    assert response.status_code == 201
    assert response.json()["title"] is None
    assert store.writes == [(USER_ID, None)]


def test_create_rejects_overlong_title(monkeypatch: pytest.MonkeyPatch) -> None:
    """Titles past the limit fail validation with 422 and write nothing."""
    store = FakeStore()
    monkeypatch.setitem(
        app.dependency_overrides,
        get_access_token_verifier,
        lambda: FakeVerifier(USER_ID),
    )
    monkeypatch.setitem(app.dependency_overrides, get_conversation_store, lambda: store)
    try:
        response = TestClient(app, raise_server_exceptions=False).post(
            "/conversations",
            json={"title": "x" * (MAX_CONVERSATION_TITLE_LENGTH + 1)},
            headers={"Authorization": "Bearer header.payload.signature"},
        )
    finally:
        app.dependency_overrides = {}

    assert response.status_code == 422
    assert store.writes == []


def test_create_accepts_title_at_the_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A title of exactly the limit is stored untouched."""
    title = "x" * MAX_CONVERSATION_TITLE_LENGTH
    store, response = post_conversation(monkeypatch, {"title": title})

    assert response.status_code == 201
    assert response.json()["title"] == title
    assert store.writes == [(USER_ID, title)]


def test_create_rejects_wrong_title_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-string title fails validation with 422 and writes nothing."""
    store = FakeStore()
    monkeypatch.setitem(
        app.dependency_overrides,
        get_access_token_verifier,
        lambda: FakeVerifier(USER_ID),
    )
    monkeypatch.setitem(app.dependency_overrides, get_conversation_store, lambda: store)
    try:
        response = TestClient(app, raise_server_exceptions=False).post(
            "/conversations",
            json={"title": 42},
            headers={"Authorization": "Bearer header.payload.signature"},
        )
    finally:
        app.dependency_overrides = {}

    assert response.status_code == 422
    assert store.writes == []


def test_create_ignores_forged_user_id_in_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A body `user_id` is dropped: the row still belongs to the caller."""
    store, response = post_conversation(
        monkeypatch, {"user_id": OTHER_USER_ID, "title": "hi"}
    )

    assert response.status_code == 201
    assert response.json()["user_id"] == USER_ID
    assert store.writes == [(USER_ID, "hi")]


def test_created_row_belongs_to_the_caller_even_for_another_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A different verified identity owns its own created row."""
    store, response = post_conversation(
        monkeypatch, {"title": "mine"}, user_id=OTHER_USER_ID
    )

    assert response.status_code == 201
    assert response.json()["user_id"] == OTHER_USER_ID
    assert store.writes == [(OTHER_USER_ID, "mine")]


def test_store_failure_returns_safe_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty insert result becomes a fixed 503, never internals."""
    _, response = post_conversation(
        monkeypatch, {}, store=FakeStore(error=ConversationCreateError("empty"))
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "The conversation could not be created."}


class RecordingTable:
    """Stand-in for the `conversations` handle: records the insert it receives."""

    def __init__(self, data: dict[str, object] | None) -> None:
        """Remember the shape the executed insert should report back."""
        self.name = ""
        self.payload: dict[str, object] = {}
        self.selected: tuple[str, ...] = ()
        self._data = data

    def insert(self, payload: dict[str, object]) -> RecordingTable:
        """Record the row payload the store wrote."""
        self.payload = payload
        return self

    def select(self, *columns: str) -> RecordingTable:
        """Record the columns the store asked to read back."""
        self.selected = columns
        return self

    def single(self) -> RecordingTable:
        """Accept the single-row variant of the insert."""
        return self

    def execute(self) -> RecordingResult:
        """Return the prepared result without touching Supabase."""
        return RecordingResult(self._data, self.payload)


class RecordingResult:
    """Stand-in for the executed insert's result."""

    def __init__(self, data: dict[str, object] | None, payload: dict[str, object]) -> None:
        """Build the row the store will read back for the written payload."""
        if data is None:
            self.data = None
            return
        row = dict(data)
        row["user_id"] = payload.get("user_id", row["user_id"])
        row["title"] = payload.get("title", row["title"])
        self.data = row


class RecordingClient:
    """Stand-in for the Supabase client: hands out one recording table."""

    def __init__(self, table: RecordingTable) -> None:
        """Bind the client to the table it should return."""
        self._table = table

    def table(self, name: str) -> RecordingTable:
        """Record the table name and return the table handle."""
        self._table.name = name
        return self._table


def make_store(table: RecordingTable) -> SupabaseConversationStore:
    """Build a store whose client factory returns the recording client."""
    return SupabaseConversationStore(Settings(), client_factory=lambda _: RecordingClient(table))


def test_insert_payload_names_caller_and_columns() -> None:
    """The store inserts into `conversations` with exactly (user_id, title)."""
    table = RecordingTable(CREATED_ROW)

    created = make_store(table).create(USER_ID, "hello")

    assert table.name == "conversations"
    assert table.payload == {"user_id": USER_ID, "title": "hello"}
    assert table.selected == ("id", "user_id", "title", "created_at", "updated_at")
    assert created.user_id == USER_ID
    assert created.title == "hello"


def test_insert_returning_no_row_is_a_safe_create_error() -> None:
    """An insert that hands back no row never becomes a half-built record."""
    table = RecordingTable(data=None)

    with pytest.raises(ConversationCreateError):
        make_store(table).create(USER_ID, "hello")

    assert table.payload == {"user_id": USER_ID, "title": "hello"}

