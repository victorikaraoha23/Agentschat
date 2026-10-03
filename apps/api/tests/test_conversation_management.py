"""Conversation management: PATCH and DELETE /conversations/{id} (Task 5.4).

Two levels, as in the retrieval tests. The *endpoint* level asserts
authentication, ownership, validation, and a not-found answer that cannot be
told apart from another user's conversation. The *store* level asserts the
statements that are really built — an owner-scoped update and an owner-scoped
delete — which is where the database is told to touch exactly one owner's row.

The store and auth dependencies are faked, so no test needs a live Supabase
project or credentials. RLS cannot run here (there is no live Postgres), and
it is not what protects these writes anyway: the backend client uses the
service-role key, so the explicit owner filters asserted below are the
enforcement. The `updated_at` refresh on rename comes from the migration's
before-update trigger (asserted in test_conversations.py); here the fake store
simulates that refresh so the endpoint contract can be checked.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient
from supabase import PostgrestAPIError

from app.auth import AuthenticatedUser, get_access_token_verifier
from app.config import Settings
from app.conversations import Conversation, SupabaseConversationStore
from app.main import MAX_CONVERSATION_TITLE_LENGTH, app, get_conversation_store

USER_ID = "123e4567-e89b-12d3-a456-426614174000"
OTHER_USER_ID = "123e4567-e89b-12d3-a456-426614174999"
TOKEN = "header.payload.signature"

CONVERSATION_ID = "223e4567-e89b-12d3-a456-426614174000"
OTHER_CONVERSATION_ID = "223e4567-e89b-12d3-a456-426614174001"
MISSING_CONVERSATION_ID = "223e4567-e89b-12d3-a456-4266141740ff"
NOT_A_UUID = "not-a-conversation-id"

NEW_CONVERSATION_ID = "323e4567-e89b-12d3-a456-426614174000"
CREATED_AT = "2026-10-03T09:00:00Z"
RENAMED_UPDATED_AT = "2026-10-04T12:30:00Z"

MY_ROW = {
    "id": CONVERSATION_ID,
    "user_id": USER_ID,
    "title": "mine",
    "created_at": CREATED_AT,
    "updated_at": "2026-10-04T09:00:00Z",
}

OTHER_ROW = {
    "id": OTHER_CONVERSATION_ID,
    "user_id": OTHER_USER_ID,
    "title": "theirs",
    "created_at": CREATED_AT,
    "updated_at": "2026-10-05T09:00:00Z",
}


class FakeVerifier:
    """Stand-in for the token verifier: accepts one bearer token."""

    def __init__(self, user_id: str) -> None:
        """Bind the verifier to the identity a valid token resolves to."""
        self._user_id = user_id

    def verify(self, access_token: str) -> AuthenticatedUser:
        """Accept the canned token and return the bound identity."""
        assert access_token == TOKEN
        return AuthenticatedUser(user_id=self._user_id)


class FakeManagementStore:
    """Stand-in for the conversation store: all five operations, one row set.

    Like the real store, rename and delete act on a row only when the caller's
    identity owns it — so an endpoint that forgot to pass that identity would
    fail here rather than quietly touching someone else's row. A rename bumps
    `updated_at` the way the database trigger does.
    """

    def __init__(
        self,
        rows: list[dict[str, object]] | None = None,
        rename_error: Exception | None = None,
        delete_error: Exception | None = None,
    ) -> None:
        """Seed the rows to operate on and the errors to raise, if any."""
        self._rows = [dict(row) for row in (rows or [])]
        self._rename_error = rename_error
        self._delete_error = delete_error
        self.renames: list[tuple[str, str, str | None]] = []
        self.deletes: list[tuple[str, str]] = []

    def _owned_row(
        self, user_id: str, conversation_id: str
    ) -> dict[str, object] | None:
        """Return the matching row only when ``user_id`` owns it."""
        for row in self._rows:
            if row["id"] == conversation_id and row["user_id"] == user_id:
                return row
        return None

    def rename_for_user(
        self, user_id: str, conversation_id: str, title: str | None
    ) -> Conversation | None:
        """Record the rename and apply it to a row this identity owns."""
        self.renames.append((user_id, conversation_id, title))
        if self._rename_error is not None:
            raise self._rename_error
        row = self._owned_row(user_id, conversation_id)
        if row is None:
            return None
        row["title"] = title
        row["updated_at"] = RENAMED_UPDATED_AT
        return Conversation.model_validate(row)

    def delete_for_user(self, user_id: str, conversation_id: str) -> bool:
        """Record the delete and remove the row only if this identity owns it."""
        self.deletes.append((user_id, conversation_id))
        if self._delete_error is not None:
            raise self._delete_error
        row = self._owned_row(user_id, conversation_id)
        if row is None:
            return False
        self._rows.remove(row)
        return True

    # The lifecycle test below drives all five operations through one store.

    def create(self, user_id: str, title: str | None) -> Conversation:
        """Append a new owned row, as the insert would."""
        row: dict[str, object] = {
            "id": NEW_CONVERSATION_ID,
            "user_id": user_id,
            "title": title,
            "created_at": CREATED_AT,
            "updated_at": CREATED_AT,
        }
        self._rows.append(row)
        return Conversation.model_validate(row)

    def list_for_user(self, user_id: str) -> list[Conversation]:
        """Return only this identity's rows."""
        return [
            Conversation.model_validate(row)
            for row in self._rows
            if row["user_id"] == user_id
        ]

    def get_for_user(self, user_id: str, conversation_id: str) -> Conversation | None:
        """Return one owned row, or nothing."""
        row = self._owned_row(user_id, conversation_id)
        return Conversation.model_validate(row) if row is not None else None


def with_auth(
    monkeypatch: pytest.MonkeyPatch, user_id: str, store: FakeManagementStore
) -> dict[str, str]:
    """Override auth + store dependencies for one request; return its headers."""
    monkeypatch.setitem(
        app.dependency_overrides,
        get_access_token_verifier,
        lambda: FakeVerifier(user_id),
    )
    monkeypatch.setitem(app.dependency_overrides, get_conversation_store, lambda: store)
    return {"Authorization": f"Bearer {TOKEN}"}


def patch_conversation(
    monkeypatch: pytest.MonkeyPatch,
    conversation_id: str,
    body: object,
    user_id: str = USER_ID,
    store: FakeManagementStore | None = None,
    authenticated: bool = True,
) -> tuple[FakeManagementStore, httpx.Response]:
    """PATCH one conversation with faked auth and store; return store + response.

    Every override is removed again afterwards, so one test's fake can never
    leak into the next.
    """
    active = store if store is not None else FakeManagementStore([MY_ROW, OTHER_ROW])
    headers: dict[str, str] = {}
    if authenticated:
        headers = with_auth(monkeypatch, user_id, active)
    try:
        response = TestClient(app, raise_server_exceptions=False).patch(
            f"/conversations/{conversation_id}",
            json=body,
            headers=headers,
        )
    finally:
        app.dependency_overrides = {}
    return active, response


def delete_conversation(
    monkeypatch: pytest.MonkeyPatch,
    conversation_id: str,
    user_id: str = USER_ID,
    store: FakeManagementStore | None = None,
    authenticated: bool = True,
) -> tuple[FakeManagementStore, httpx.Response]:
    """DELETE one conversation with faked auth and store; return store + response."""
    active = store if store is not None else FakeManagementStore([MY_ROW, OTHER_ROW])
    headers: dict[str, str] = {}
    if authenticated:
        headers = with_auth(monkeypatch, user_id, active)
    try:
        response = TestClient(app, raise_server_exceptions=False).delete(
            f"/conversations/{conversation_id}",
            headers=headers,
        )
    finally:
        app.dependency_overrides = {}
    return active, response


def get(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    user_id: str = USER_ID,
    store: FakeManagementStore | None = None,
) -> httpx.Response:
    """GET one path against the given store with faked auth; return the response."""
    active = store if store is not None else FakeManagementStore([MY_ROW, OTHER_ROW])
    headers = with_auth(monkeypatch, user_id, active)
    try:
        response = TestClient(app, raise_server_exceptions=False).get(
            path, headers=headers
        )
    finally:
        app.dependency_overrides = {}
    return response


def post(
    monkeypatch: pytest.MonkeyPatch,
    body: object,
    user_id: str,
    store: FakeManagementStore,
) -> httpx.Response:
    """POST /conversations against the given store; return the response."""
    headers = with_auth(monkeypatch, user_id, store)
    try:
        response = TestClient(app, raise_server_exceptions=False).post(
            "/conversations",
            json=body,
            headers=headers,
        )
    finally:
        app.dependency_overrides = {}
    return response


# --------------------------------------------------------------------------
# Rename: PATCH /conversations/{conversation_id}
# --------------------------------------------------------------------------


def test_unauthenticated_rename_is_rejected() -> None:
    """No bearer token means the 401 authentication error, never a rename."""
    response = TestClient(app).patch(f"/conversations/{CONVERSATION_ID}", json={})

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


def test_rename_updates_title_and_returns_the_conversation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An authenticated rename of an owned conversation answers with the row."""
    store, response = patch_conversation(
        monkeypatch, CONVERSATION_ID, {"title": "renamed"}
    )

    assert response.status_code == 200
    assert response.json() == dict(
        MY_ROW, title="renamed", updated_at=RENAMED_UPDATED_AT
    )
    assert store.renames == [(USER_ID, CONVERSATION_ID, "renamed")]


def test_rename_persists_owner_and_created_at_and_refreshes_updated_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the title and `updated_at` change: owner and creation time stand."""
    _, response = patch_conversation(monkeypatch, CONVERSATION_ID, {"title": "renamed"})
    row = response.json()

    assert row["title"] == "renamed"
    assert row["user_id"] == USER_ID
    assert row["created_at"] == CREATED_AT
    assert row["updated_at"] == RENAMED_UPDATED_AT
    assert row["updated_at"] != MY_ROW["updated_at"]


def test_rename_trims_surrounding_whitespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Surrounding whitespace is trimmed before the row is written — one rule set."""
    store, response = patch_conversation(
        monkeypatch, CONVERSATION_ID, {"title": "  hello  "}
    )

    assert response.status_code == 200
    assert response.json()["title"] == "hello"
    assert store.renames == [(USER_ID, CONVERSATION_ID, "hello")]


def test_rename_with_empty_or_blank_title_clears_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty and whitespace-only titles follow the creation rule: stored as NULL."""
    empty_store, empty = patch_conversation(monkeypatch, CONVERSATION_ID, {"title": ""})
    blank_store, blank = patch_conversation(
        monkeypatch, CONVERSATION_ID, {"title": "   "}
    )

    assert empty.status_code == 200
    assert empty.json()["title"] is None
    assert empty_store.renames == [(USER_ID, CONVERSATION_ID, None)]
    assert blank.status_code == 200
    assert blank.json()["title"] is None
    assert blank_store.renames == [(USER_ID, CONVERSATION_ID, None)]


def test_rename_with_explicit_null_title_clears_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`null` is the same as blank — the title type matches creation exactly."""
    store, response = patch_conversation(monkeypatch, CONVERSATION_ID, {"title": None})

    assert response.status_code == 200
    assert response.json()["title"] is None
    assert store.renames == [(USER_ID, CONVERSATION_ID, None)]


def test_rename_rejects_overlong_title(monkeypatch: pytest.MonkeyPatch) -> None:
    """Titles past the limit fail validation with 422 and touch nothing."""
    store = FakeManagementStore([MY_ROW])
    _, response = patch_conversation(
        monkeypatch,
        CONVERSATION_ID,
        {"title": "x" * (MAX_CONVERSATION_TITLE_LENGTH + 1)},
        store=store,
    )

    assert response.status_code == 422
    assert store.renames == []


def test_rename_accepts_title_at_the_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """A title of exactly the limit is stored untouched."""
    title = "x" * MAX_CONVERSATION_TITLE_LENGTH
    store, response = patch_conversation(monkeypatch, CONVERSATION_ID, {"title": title})

    assert response.status_code == 200
    assert response.json()["title"] == title
    assert store.renames == [(USER_ID, CONVERSATION_ID, title)]


def test_rename_rejects_missing_title(monkeypatch: pytest.MonkeyPatch) -> None:
    """A body without a title is malformed: 422, and no rename runs."""
    store = FakeManagementStore([MY_ROW])
    _, response = patch_conversation(monkeypatch, CONVERSATION_ID, {}, store=store)

    assert response.status_code == 422
    assert store.renames == []


def test_rename_rejects_wrong_title_type(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-string title fails validation with 422 and touches nothing."""
    store = FakeManagementStore([MY_ROW])
    _, response = patch_conversation(
        monkeypatch, CONVERSATION_ID, {"title": 42}, store=store
    )

    assert response.status_code == 422
    assert store.renames == []


def test_rename_with_invalid_path_id_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-UUID path segment fails validation before any store call."""
    store = FakeManagementStore([MY_ROW])
    _, response = patch_conversation(
        monkeypatch, NOT_A_UUID, {"title": "hello"}, store=store
    )

    assert response.status_code == 422
    assert store.renames == []


def test_rename_ignores_forged_user_id_in_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A body `user_id` is dropped: the rename still runs for the caller."""
    store, response = patch_conversation(
        monkeypatch,
        CONVERSATION_ID,
        {"title": "hi", "user_id": OTHER_USER_ID},
    )

    assert response.status_code == 200
    assert response.json()["user_id"] == USER_ID
    assert store.renames == [(USER_ID, CONVERSATION_ID, "hi")]


def test_user_cannot_rename_another_users_conversation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A → B is a 404 with the standard body; B's row is left untouched."""
    store, response = patch_conversation(
        monkeypatch, OTHER_CONVERSATION_ID, {"title": "hijacked"}
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Conversation not found."}
    assert store.renames == [(USER_ID, OTHER_CONVERSATION_ID, "hijacked")]
    foreign = store.get_for_user(OTHER_USER_ID, OTHER_CONVERSATION_ID)
    assert foreign is not None
    assert foreign.title == "theirs"


def test_missing_and_foreign_renames_answer_identically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rename can never confirm that someone else's conversation exists."""
    _, foreign = patch_conversation(monkeypatch, OTHER_CONVERSATION_ID, {"title": "x"})
    _, missing = patch_conversation(
        monkeypatch, MISSING_CONVERSATION_ID, {"title": "x"}
    )

    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()


def test_each_user_renames_only_their_own_conversation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A renames A, A cannot rename B, B renames B — enforcement is per identity."""
    _, own = patch_conversation(monkeypatch, CONVERSATION_ID, {"title": "a's title"})
    _, cross = patch_conversation(monkeypatch, OTHER_CONVERSATION_ID, {"title": "nope"})
    _, theirs = patch_conversation(
        monkeypatch,
        OTHER_CONVERSATION_ID,
        {"title": "b's title"},
        user_id=OTHER_USER_ID,
    )

    assert own.status_code == 200
    assert cross.status_code == 404
    assert theirs.status_code == 200
    assert theirs.json()["title"] == "b's title"


def test_rename_maps_a_failing_store_to_a_safe_503(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failed rename is a fixed 503, never provider text or SQL."""
    failure = PostgrestAPIError({"message": "private provider detail", "code": "XX000"})
    _, response = patch_conversation(
        monkeypatch,
        CONVERSATION_ID,
        {"title": "hello"},
        store=FakeManagementStore([MY_ROW], rename_error=failure),
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "The conversation could not be updated."}
    assert "private provider detail" not in response.text
    assert "private provider detail" not in caplog.text


def test_broken_renamed_row_is_a_safe_500(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A row that cannot be parsed is an internal failure, not a leaked payload."""
    broken_row = dict(MY_ROW, created_at="not-a-timestamp", title="private row value")
    _, response = patch_conversation(
        monkeypatch,
        CONVERSATION_ID,
        {"title": "hello"},
        store=FakeManagementStore([broken_row]),
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error."}
    for leaked in ("not-a-timestamp", "private row value"):
        assert leaked not in response.text
        assert leaked not in caplog.text


# --------------------------------------------------------------------------
# Delete: DELETE /conversations/{conversation_id}
# --------------------------------------------------------------------------


def test_unauthenticated_delete_is_rejected() -> None:
    """No bearer token means the 401 authentication error, never a deletion."""
    response = TestClient(app).delete(f"/conversations/{CONVERSATION_ID}")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


def test_delete_removes_the_owners_conversation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An authenticated delete of an owned conversation answers 204, no body."""
    store, response = delete_conversation(monkeypatch, CONVERSATION_ID)

    assert response.status_code == 204
    assert response.content == b""
    assert store.deletes == [(USER_ID, CONVERSATION_ID)]
    assert store.get_for_user(USER_ID, CONVERSATION_ID) is None


def test_deleted_conversation_is_gone_from_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After deletion the conversation is missing from retrieval *and* listing."""
    store = FakeManagementStore([MY_ROW, OTHER_ROW])
    _, deleted = delete_conversation(monkeypatch, CONVERSATION_ID, store=store)
    retrieved = get(monkeypatch, f"/conversations/{CONVERSATION_ID}", store=store)
    listed = get(monkeypatch, "/conversations", store=store)

    assert deleted.status_code == 204
    assert retrieved.status_code == 404
    assert retrieved.json() == {"detail": "Conversation not found."}
    assert listed.status_code == 200
    # The owner's list no longer contains the deleted conversation; the other
    # user's row was never in this list to begin with (owner-scoped read).
    assert listed.json() == {"items": []}


def test_user_cannot_delete_another_users_conversation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A → B is a 404 with the standard body; B's row still exists."""
    store, response = delete_conversation(monkeypatch, OTHER_CONVERSATION_ID)

    assert response.status_code == 404
    assert response.json() == {"detail": "Conversation not found."}
    assert store.deletes == [(USER_ID, OTHER_CONVERSATION_ID)]
    assert store.get_for_user(OTHER_USER_ID, OTHER_CONVERSATION_ID) is not None


def test_missing_and_foreign_deletes_answer_identically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A delete can never confirm that someone else's conversation exists."""
    _, foreign = delete_conversation(monkeypatch, OTHER_CONVERSATION_ID)
    _, missing = delete_conversation(monkeypatch, MISSING_CONVERSATION_ID)

    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()


def test_delete_leaves_other_users_conversations_intact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deleting A's conversation never touches B's: B still reads its own row."""
    store = FakeManagementStore([MY_ROW, OTHER_ROW])
    _, deleted = delete_conversation(monkeypatch, CONVERSATION_ID, store=store)
    theirs = get(
        monkeypatch,
        f"/conversations/{OTHER_CONVERSATION_ID}",
        user_id=OTHER_USER_ID,
        store=store,
    )

    assert deleted.status_code == 204
    assert theirs.status_code == 200
    assert theirs.json() == OTHER_ROW


def test_delete_with_invalid_path_id_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-UUID path segment fails validation before any store call."""
    store = FakeManagementStore([MY_ROW])
    _, response = delete_conversation(monkeypatch, NOT_A_UUID, store=store)

    assert response.status_code == 422
    assert store.deletes == []


def test_delete_maps_a_failing_store_to_a_safe_503(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failed delete is a fixed 503, never provider text or SQL."""
    failure = PostgrestAPIError({"message": "private provider detail", "code": "XX000"})
    _, response = delete_conversation(
        monkeypatch,
        CONVERSATION_ID,
        store=FakeManagementStore([MY_ROW], delete_error=failure),
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "The conversation could not be deleted."}
    assert "private provider detail" not in response.text
    assert "private provider detail" not in caplog.text


# --------------------------------------------------------------------------
# Store-level statements (what the database is actually asked to do)
# --------------------------------------------------------------------------


class RecordingResult:
    """Stand-in for an executed write's result."""

    def __init__(self, data: dict[str, object] | None) -> None:
        """Expose the prepared payload through the result's data field."""
        self.data = data


class RecordingWriteQuery:
    """The update/delete chain, recording what the store asked for."""

    def __init__(self, result: RecordingResult | None) -> None:
        """Prepare the result the executed query should hand back."""
        self.filters: list[tuple[str, object]] = []
        self.selected: tuple[str, ...] = ()
        self.single_row = False
        self._result = result

    def eq(self, column: str, value: object) -> RecordingWriteQuery:
        """Record an equality filter."""
        self.filters.append((column, value))
        return self

    def select(self, *columns: str) -> RecordingWriteQuery:
        """Record the columns the write returns."""
        self.selected = columns
        return self

    def maybe_single(self) -> RecordingWriteQuery:
        """Record that this write accepts zero or one row."""
        self.single_row = True
        return self

    def execute(self) -> RecordingResult | None:
        """Return the prepared result without touching Supabase."""
        return self._result


class RecordingWriteTable:
    """Stand-in for the `conversations` handle: records one write."""

    def __init__(self, result: RecordingResult | None) -> None:
        """Bind the table to the result its write should return."""
        self.name = ""
        self.updated: dict[str, object] | None = None
        self.deleted = False
        self.query = RecordingWriteQuery(result)

    def update(self, payload: dict[str, object]) -> RecordingWriteQuery:
        """Record the update payload."""
        self.updated = payload
        return self.query

    def delete(self) -> RecordingWriteQuery:
        """Record that a delete was requested."""
        self.deleted = True
        return self.query


class RecordingClient:
    """Stand-in for the Supabase client: hands out one recording table."""

    def __init__(self, table: RecordingWriteTable) -> None:
        """Bind the client to the table it should return."""
        self._table = table

    def table(self, name: str) -> RecordingWriteTable:
        """Record the table name and return the table handle."""
        self._table.name = name
        return self._table


def make_store(
    result: RecordingResult | None,
) -> tuple[SupabaseConversationStore, RecordingWriteTable]:
    """Build a store whose client factory returns a recording client."""
    table = RecordingWriteTable(result)
    store = SupabaseConversationStore(
        Settings(), client_factory=lambda _: RecordingClient(table)
    )
    return store, table


def test_rename_statement_is_owner_scoped_and_returns_the_row() -> None:
    """The update filters on id *and* owner, then reads the row back."""
    store, table = make_store(RecordingResult(dict(MY_ROW, title="renamed")))

    renamed = store.rename_for_user(USER_ID, CONVERSATION_ID, "renamed")

    assert table.name == "conversations"
    assert table.updated == {"title": "renamed"}
    assert table.query.filters == [("id", CONVERSATION_ID), ("user_id", USER_ID)]
    assert table.query.selected == (
        "id",
        "user_id",
        "title",
        "created_at",
        "updated_at",
    )
    assert table.query.single_row is True
    assert renamed is not None
    assert renamed.title == "renamed"


def test_rename_matching_no_row_is_nothing() -> None:
    """A foreign id and a nonexistent id both come back as "no row"."""
    absent, _ = make_store(None)
    no_data, _ = make_store(RecordingResult(None))

    assert absent.rename_for_user(USER_ID, OTHER_CONVERSATION_ID, "x") is None
    assert no_data.rename_for_user(USER_ID, OTHER_CONVERSATION_ID, "x") is None


def test_delete_statement_is_owner_scoped() -> None:
    """The delete filters on id *and* owner before anything is removed."""
    store, table = make_store(RecordingResult(dict(MY_ROW)))

    deleted = store.delete_for_user(USER_ID, CONVERSATION_ID)

    assert table.name == "conversations"
    assert table.deleted is True
    assert table.updated is None
    assert table.query.filters == [("id", CONVERSATION_ID), ("user_id", USER_ID)]
    assert table.query.single_row is True
    assert deleted is True


def test_delete_matching_no_row_reports_failure() -> None:
    """A foreign id and a nonexistent id both come back as "nothing deleted"."""
    absent, _ = make_store(None)
    no_data, _ = make_store(RecordingResult(None))

    assert absent.delete_for_user(USER_ID, OTHER_CONVERSATION_ID) is False
    assert no_data.delete_for_user(USER_ID, OTHER_CONVERSATION_ID) is False


# --------------------------------------------------------------------------
# Whole-lifecycle regression: create → retrieve → rename → list → delete
# --------------------------------------------------------------------------


def test_full_lifecycle_create_retrieve_rename_list_delete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All five conversation operations work together on one store, in order."""
    store = FakeManagementStore()

    created = post(monkeypatch, {"title": "start"}, USER_ID, store)
    assert created.status_code == 201
    assert created.json()["id"] == NEW_CONVERSATION_ID

    first_read = get(monkeypatch, f"/conversations/{NEW_CONVERSATION_ID}", store=store)
    assert first_read.status_code == 200
    assert first_read.json()["title"] == "start"

    _, renamed = patch_conversation(
        monkeypatch, NEW_CONVERSATION_ID, {"title": "renamed"}, store=store
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "renamed"

    updated_read = get(
        monkeypatch, f"/conversations/{NEW_CONVERSATION_ID}", store=store
    )
    assert updated_read.status_code == 200
    assert updated_read.json()["title"] == "renamed"

    listed = get(monkeypatch, "/conversations", store=store)
    assert listed.status_code == 200
    assert [row["title"] for row in listed.json()["items"]] == ["renamed"]

    _, deleted = delete_conversation(monkeypatch, NEW_CONVERSATION_ID, store=store)
    assert deleted.status_code == 204

    gone = get(monkeypatch, f"/conversations/{NEW_CONVERSATION_ID}", store=store)
    assert gone.status_code == 404
    assert gone.json() == {"detail": "Conversation not found."}

    empty = get(monkeypatch, "/conversations", store=store)
    assert empty.status_code == 200
    assert empty.json() == {"items": []}
