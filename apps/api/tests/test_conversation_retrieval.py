"""Conversation retrieval: GET /conversations and GET /conversations/{id} (Task 5.3).

Two levels are covered, because two different things can break. The *endpoint*
level asserts authentication, ownership, and a not-found answer that cannot be
told apart from another user's conversation. The *store* level asserts the query
that is really built — owner filter, deterministic ordering, at-most-one-row
read — which is where the database is told to scope and order the result.

The store's read chain and the endpoint's dependencies are faked, so no test
needs a live Supabase project or credentials. RLS cannot run here (there is no
live Postgres), and it is not what protects these reads anyway: the backend
client uses the service-role key, so the explicit owner filter asserted below is
the enforcement, not a second line of defence.
"""

from __future__ import annotations

from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from supabase import PostgrestAPIError, SupabaseException

from app.auth import AuthenticatedUser, get_access_token_verifier
from app.config import Settings
from app.conversations import Conversation, SupabaseConversationStore
from app.main import app, get_conversation_store
from app.supabase_client import SupabaseNotConfiguredError

USER_ID = "123e4567-e89b-12d3-a456-426614174000"
OTHER_USER_ID = "123e4567-e89b-12d3-a456-426614174999"
TOKEN = "header.payload.signature"

CONVERSATION_ID = "223e4567-e89b-12d3-a456-426614174000"
OTHER_CONVERSATION_ID = "223e4567-e89b-12d3-a456-426614174001"
MISSING_CONVERSATION_ID = "223e4567-e89b-12d3-a456-4266141740ff"
NOT_A_UUID = "not-a-conversation-id"

MY_ROW = {
    "id": CONVERSATION_ID,
    "user_id": USER_ID,
    "title": "mine",
    "created_at": "2026-10-03T09:00:00Z",
    "updated_at": "2026-10-04T09:00:00Z",
}

OTHER_ROW = {
    "id": OTHER_CONVERSATION_ID,
    "user_id": OTHER_USER_ID,
    "title": "theirs",
    "created_at": "2026-10-03T09:00:00Z",
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


class FakeReadStore:
    """Stand-in for the conversation store, implementing only the reads.

    It applies the same owner rule the real store pushes into the query — a row
    is returned only when its owner is the identity being asked about — so an
    endpoint that forgot to pass that identity would fail here rather than
    quietly serving someone else's row.
    """

    def __init__(
        self,
        rows: list[dict[str, object]] | None = None,
        error: Exception | None = None,
    ) -> None:
        """Seed the rows to serve and the error every read should raise, if any."""
        self._rows = list(rows or [])
        self._error = error
        self.listed_for: list[str] = []
        self.requested: list[tuple[str, str]] = []

    def list_for_user(self, user_id: str) -> list[Conversation]:
        """Record the identity asked about and return the rows that identity owns."""
        self.listed_for.append(user_id)
        if self._error is not None:
            raise self._error
        return [
            Conversation.model_validate(row)
            for row in self._rows
            if row["user_id"] == user_id
        ]

    def get_for_user(self, user_id: str, conversation_id: str) -> Conversation | None:
        """Record the lookup and return the row only if this identity owns it."""
        self.requested.append((user_id, conversation_id))
        if self._error is not None:
            raise self._error
        for row in self._rows:
            if row["id"] == conversation_id and row["user_id"] == user_id:
                return Conversation.model_validate(row)
        return None


def get(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    user_id: str = USER_ID,
    store: FakeReadStore | None = None,
    authenticated: bool = True,
) -> tuple[FakeReadStore, httpx.Response]:
    """GET ``path`` with faked auth and store; return that store and the response.

    Every override is removed again afterwards, so one test's fake can never
    leak into the next.
    """
    active = store if store is not None else FakeReadStore([MY_ROW, OTHER_ROW])
    headers: dict[str, str] = {}
    if authenticated:
        headers["Authorization"] = f"Bearer {TOKEN}"
        monkeypatch.setitem(
            app.dependency_overrides,
            get_access_token_verifier,
            lambda: FakeVerifier(user_id),
        )
        monkeypatch.setitem(
            app.dependency_overrides, get_conversation_store, lambda: active
        )
    try:
        response = TestClient(app, raise_server_exceptions=False).get(path, headers=headers)
    finally:
        app.dependency_overrides = {}
    return active, response


def test_unauthenticated_list_is_rejected() -> None:
    """No bearer token means the 401 authentication error, never a collection."""
    response = TestClient(app).get("/conversations")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


def test_list_returns_only_the_callers_conversations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The verified caller gets their own row — and never the other owner's row."""
    store, response = get(monkeypatch, "/conversations")

    assert response.status_code == 200
    assert response.json() == {"items": [MY_ROW]}
    assert store.listed_for == [USER_ID]


def test_list_scopes_the_query_to_the_signed_in_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A different signed-in user is asked about as that user, not as the first."""
    store, response = get(monkeypatch, "/conversations", user_id=OTHER_USER_ID)

    assert response.status_code == 200
    assert response.json() == {"items": [OTHER_ROW]}
    assert store.listed_for == [OTHER_USER_ID]


def test_list_ignores_a_user_id_query_parameter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ownership never comes from the request, so the parameter is not an input."""
    store, response = get(monkeypatch, f"/conversations?user_id={OTHER_USER_ID}")

    assert response.status_code == 200
    assert response.json() == {"items": [MY_ROW]}
    assert store.listed_for == [USER_ID]


def test_list_items_expose_only_documented_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Items carry the conversation contract and nothing beyond it."""
    _, response = get(monkeypatch, "/conversations")

    (item,) = response.json()["items"]
    assert set(item) == {"id", "user_id", "title", "created_at", "updated_at"}


def test_empty_account_returns_an_empty_collection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A user with no conversations gets 200 and an empty list, not an error."""
    store, response = get(monkeypatch, "/conversations", store=FakeReadStore([]))

    assert response.status_code == 200
    assert response.json() == {"items": []}
    assert store.listed_for == [USER_ID]


@pytest.mark.parametrize(
    "failure",
    [
        PostgrestAPIError({"message": "private provider detail", "code": "XX000"}),
        SupabaseException("private provider detail"),
        SupabaseNotConfiguredError("private provider detail"),
        httpx.ConnectError("private provider detail"),
        httpx.ReadTimeout("private provider detail"),
    ],
)
def test_list_maps_a_failing_read_to_a_safe_503(
    failure: Exception,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A read failure has the same safe shape whichever layer failed."""
    _, response = get(
        monkeypatch, "/conversations", store=FakeReadStore([MY_ROW], error=failure)
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "The conversations could not be read."}
    assert "private provider detail" not in response.text
    assert "private provider detail" not in caplog.text


def test_unauthenticated_read_is_rejected() -> None:
    """No bearer token means the 401 authentication error, never a conversation."""
    response = TestClient(app).get(f"/conversations/{CONVERSATION_ID}")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


def test_read_returns_the_callers_conversation(monkeypatch: pytest.MonkeyPatch) -> None:
    """An authenticated caller reads their own conversation by id."""
    store, response = get(monkeypatch, f"/conversations/{CONVERSATION_ID}")

    assert response.status_code == 200
    assert response.json() == MY_ROW
    assert store.requested == [(USER_ID, CONVERSATION_ID)]


def test_unknown_conversation_id_is_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """An id with no matching row is a 404 that says nothing else."""
    store, response = get(monkeypatch, f"/conversations/{MISSING_CONVERSATION_ID}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Conversation not found."}
    assert store.requested == [(USER_ID, MISSING_CONVERSATION_ID)]
    assert MISSING_CONVERSATION_ID not in response.text


def test_another_users_conversation_looks_exactly_like_a_missing_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both cases return identical responses: existence is never confirmed."""
    _, foreign = get(monkeypatch, f"/conversations/{OTHER_CONVERSATION_ID}")
    _, missing = get(monkeypatch, f"/conversations/{MISSING_CONVERSATION_ID}")

    assert foreign.status_code == 404
    assert foreign.json() == missing.json()
    assert OTHER_CONVERSATION_ID not in foreign.text
    assert OTHER_USER_ID not in foreign.text


def test_invalid_conversation_id_is_rejected_before_any_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A path segment that is not a UUID fails validation and reads nothing."""
    store, response = get(monkeypatch, f"/conversations/{NOT_A_UUID}")

    assert response.status_code == 422
    assert store.requested == []


def test_ownership_matrix_allows_only_the_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    """A reads A, A cannot read B, and B reads B — enforcement is per identity."""
    _, own = get(monkeypatch, f"/conversations/{CONVERSATION_ID}", user_id=USER_ID)
    _, cross = get(
        monkeypatch, f"/conversations/{OTHER_CONVERSATION_ID}", user_id=USER_ID
    )
    _, theirs = get(
        monkeypatch, f"/conversations/{OTHER_CONVERSATION_ID}", user_id=OTHER_USER_ID
    )

    assert own.status_code == 200
    assert cross.status_code == 404
    assert cross.json() == {"detail": "Conversation not found."}
    assert theirs.status_code == 200
    assert theirs.json() == OTHER_ROW


def test_read_maps_a_failing_store_to_a_safe_503(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failed read is a fixed 503, never provider text or SQL."""
    failure = PostgrestAPIError({"message": "private provider detail", "code": "XX000"})
    _, response = get(
        monkeypatch,
        f"/conversations/{CONVERSATION_ID}",
        store=FakeReadStore([MY_ROW], error=failure),
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "The conversation could not be read."}
    assert "private provider detail" not in response.text
    assert "private provider detail" not in caplog.text


def test_row_that_breaks_the_conversation_contract_is_a_safe_500(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A row that cannot be parsed is an internal failure, not a leaked payload."""
    broken_row = {
        "id": "definitely-not-a-uuid",
        "user_id": USER_ID,
        "title": "private row value",
        "created_at": "2026-10-03T09:00:00Z",
        "updated_at": "2026-10-03T09:00:00Z",
    }
    _, response = get(monkeypatch, "/conversations", store=FakeReadStore([broken_row]))

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error."}
    for leaked in ("definitely-not-a-uuid", "private row value"):
        assert leaked not in response.text
        assert leaked not in caplog.text


class RecordingResult:
    """Stand-in for the executed read's result."""

    def __init__(self, data: object) -> None:
        """Expose the prepared payload through the result's data field."""
        self.data = data


class RecordingSelectQuery:
    """The read chain, recording what the store asked the database for."""

    def __init__(self, result: RecordingResult | None) -> None:
        """Prepare the result the executed query should hand back."""
        self.filters: list[tuple[str, object]] = []
        self.orders: list[tuple[str, bool]] = []
        self.single_row = False
        self._result = result

    def eq(self, column: str, value: object) -> RecordingSelectQuery:
        """Record an equality filter."""
        self.filters.append((column, value))
        return self

    def order(self, column: str, *, desc: bool = False) -> RecordingSelectQuery:
        """Record an ordering instruction."""
        self.orders.append((column, desc))
        return self

    def maybe_single(self) -> RecordingSelectQuery:
        """Record that this read accepts zero or one row."""
        self.single_row = True
        return self

    def execute(self) -> RecordingResult | None:
        """Return the prepared result without touching Supabase."""
        return self._result


class RecordingTable:
    """Stand-in for the `conversations` handle: hands out one recorded read."""

    def __init__(self, query: RecordingSelectQuery) -> None:
        """Bind the table to the query it should return."""
        self.name = ""
        self.selected: tuple[str, ...] = ()
        self._query = query

    def select(self, *columns: str) -> RecordingSelectQuery:
        """Record the columns the store asked to read."""
        self.selected = columns
        return self._query


class RecordingClient:
    """Stand-in for the Supabase client: hands out one recording table."""

    def __init__(self, table: RecordingTable) -> None:
        """Bind the client to the table it should return."""
        self._table = table

    def table(self, name: str) -> RecordingTable:
        """Record the table name and return the table handle."""
        self._table.name = name
        return self._table


def make_store(
    result: RecordingResult | None,
) -> tuple[SupabaseConversationStore, RecordingTable, RecordingSelectQuery]:
    """Build a store whose client factory returns a recording client."""
    query = RecordingSelectQuery(result)
    table = RecordingTable(query)
    store = SupabaseConversationStore(
        Settings(), client_factory=lambda _: RecordingClient(table)
    )
    return store, table, query


def test_list_query_is_owner_scoped_and_deterministically_ordered() -> None:
    """The list read filters by owner in the database and orders newest first."""
    listed = [
        dict(MY_ROW, title="newest"),
        dict(MY_ROW, id=OTHER_CONVERSATION_ID, title=None),
    ]
    store, table, query = make_store(RecordingResult(listed))

    rows = store.list_for_user(USER_ID)

    assert table.name == "conversations"
    assert table.selected == ("id", "user_id", "title", "created_at", "updated_at")
    assert query.filters == [("user_id", USER_ID)]
    assert query.orders == [("updated_at", True), ("id", True)]
    assert query.single_row is False
    assert [row.title for row in rows] == ["newest", None]


def test_list_without_rows_is_an_empty_list() -> None:
    """Both shapes the SDK can report for "no rows" become an empty list."""
    empty, _, _ = make_store(RecordingResult([]))
    absent, _, _ = make_store(None)

    assert empty.list_for_user(USER_ID) == []
    assert absent.list_for_user(USER_ID) == []


def test_get_query_is_scoped_to_the_owner_and_reads_at_most_one_row() -> None:
    """The single read filters on id *and* owner, then runs as a one-row read."""
    store, table, query = make_store(RecordingResult(dict(MY_ROW)))

    conversation = store.get_for_user(USER_ID, CONVERSATION_ID)

    assert table.selected == ("id", "user_id", "title", "created_at", "updated_at")
    assert query.filters == [("id", CONVERSATION_ID), ("user_id", USER_ID)]
    assert query.orders == []
    assert query.single_row is True
    assert conversation is not None
    assert conversation.user_id == UUID(USER_ID)


def test_get_without_a_matching_row_is_nothing() -> None:
    """A foreign id and a nonexistent id both come back as "no row"."""
    absent, _, _ = make_store(None)
    no_data, _, _ = make_store(RecordingResult(None))

    assert absent.get_for_user(USER_ID, OTHER_CONVERSATION_ID) is None
    assert no_data.get_for_user(USER_ID, OTHER_CONVERSATION_ID) is None
