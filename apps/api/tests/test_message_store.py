"""Message store statements: ownership scoping before any write (Task 6.2).

The client is a recording double, so these tests assert what the store asked
Supabase to do â€” which tables, which filters, which payload â€” without a project,
credentials, or a network call. Ownership is the point: the conversation is read
with the verified identity in one statement, and a conversation the caller does
not own must not reach the insert at all.
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.messages import (
    MESSAGE_COLUMNS,
    Message,
    MessageCreateError,
    SupabaseMessageStore,
)

USER_ID = "123e4567-e89b-12d3-a456-426614174000"
OTHER_USER_ID = "123e4567-e89b-12d3-a456-426614174999"
CONVERSATION_ID = "223e4567-e89b-12d3-a456-426614174000"

INSERTED_ROW: dict[str, object] = {
    "id": "323e4567-e89b-12d3-a456-426614174000",
    "conversation_id": CONVERSATION_ID,
    "user_id": USER_ID,
    "role": "user",
    "content": "Hello",
    "created_at": "2026-10-04T12:00:00Z",
}


class RecordingResult:
    """Stand-in for an executed statement's result."""

    def __init__(self, data: object) -> None:
        """Expose the prepared payload through the result's data field."""
        self.data = data


class RecordingQuery:
    """The read chain: records columns and equality filters."""

    def __init__(self, result: RecordingResult | None) -> None:
        """Prepare the result this read should hand back."""
        self.filters: list[tuple[str, object]] = []
        self.selected: tuple[str, ...] = ()
        self.used_maybe_single = False
        self._result = result

    def select(self, *columns: str) -> RecordingQuery:
        """Record the columns the read selects."""
        self.selected = columns
        return self

    def eq(self, column: str, value: object) -> RecordingQuery:
        """Record an equality filter."""
        self.filters.append((column, value))
        return self

    def maybe_single(self) -> RecordingQuery:
        """Record that the read accepts zero rows."""
        self.used_maybe_single = True
        return self

    def execute(self) -> RecordingResult | None:
        """Return the prepared result without touching Supabase."""
        return self._result


class RecordingInsertQuery:
    """The insert chain: records the payload, the columns, and the result."""

    def __init__(self, result: RecordingResult | None) -> None:
        """Prepare the result this insert should hand back."""
        self.payload: dict[str, object] | None = None
        self.selected: tuple[str, ...] = ()
        self.used_single = False
        self._result = result

    def select(self, *columns: str) -> RecordingInsertQuery:
        """Record the columns the insert returns."""
        self.selected = columns
        return self

    def single(self) -> RecordingInsertQuery:
        """Record that the insert requires exactly one row back."""
        self.used_single = True
        return self

    def execute(self) -> RecordingResult | None:
        """Return the prepared result without touching Supabase."""
        return self._result


class RecordingTable:
    """Stand-in for one table handle: records reads and the single insert."""

    def __init__(
        self, read_result: RecordingResult | None, insert_result: RecordingResult | None
    ) -> None:
        """Bind the table to the results its statements should return."""
        self.read = RecordingQuery(read_result)
        self.insert_query = RecordingInsertQuery(insert_result)

    def select(self, *columns: str) -> RecordingQuery:
        """Start a column-scoped read."""
        return self.read.select(*columns)

    def insert(self, payload: dict[str, object]) -> RecordingInsertQuery:
        """Record the insert payload and start the insert chain."""
        self.insert_query.payload = payload
        return self.insert_query


class RecordingClient:
    """Stand-in for the Supabase client: one recording handle per table name."""

    def __init__(
        self,
        conversations: RecordingTable,
        messages: RecordingTable,
        names: list[str],
    ) -> None:
        """Bind the client to the handles it should hand out, recording names."""
        self._tables = {"conversations": conversations, "messages": messages}
        self._names = names

    def table(self, name: str) -> RecordingTable:
        """Record the table name and return its handle."""
        self._names.append(name)
        return self._tables[name]




def make_store(
    owned: object = {"id": CONVERSATION_ID},
    inserted_row: dict[str, object] | None = INSERTED_ROW,
) -> tuple[SupabaseMessageStore, RecordingTable, RecordingTable, list[str]]:
    """Build a store whose client factory returns recording handles.

    Pass `owned=None` for a conversation the caller does not own, and
    `inserted_row=None` for an insert the database did not confirm.
    """
    names: list[str] = []
    insert_data = dict(inserted_row) if inserted_row is not None else None
    conversations = RecordingTable(RecordingResult(owned), RecordingResult(None))
    messages = RecordingTable(RecordingResult(None), RecordingResult(insert_data))
    store = SupabaseMessageStore(
        Settings(), client_factory=lambda _: RecordingClient(conversations, messages, names)
    )
    return store, conversations, messages, names


def test_conversation_is_read_with_the_id_and_the_verified_owner() -> None:
    """The ownership check filters on id *and* owner in one statement."""
    store, conversations, messages, names = make_store()

    store.create_for_user(USER_ID, CONVERSATION_ID, "Hello")

    assert names == ["conversations", "messages"]
    assert conversations.read.selected == ("id",)
    assert conversations.read.filters == [("id", CONVERSATION_ID), ("user_id", USER_ID)]
    assert conversations.read.used_maybe_single is True


def test_inserted_row_names_the_caller_the_conversation_and_the_user_role() -> None:
    """The payload is exactly the four columns the schema requires."""
    store, _conversations, messages, _names = make_store()

    store.create_for_user(USER_ID, CONVERSATION_ID, "Hello")

    assert messages.insert_query.payload == {
        "conversation_id": CONVERSATION_ID,
        "user_id": USER_ID,
        "role": "user",
        "content": "Hello",
    }
    assert messages.insert_query.selected == MESSAGE_COLUMNS
    assert messages.insert_query.used_single is True


def test_the_application_never_writes_timestamps() -> None:
    """`created_at` and the conversation's `updated_at` belong to the database."""
    store, _conversations, messages, _names = make_store()

    store.create_for_user(USER_ID, CONVERSATION_ID, "Hello")

    payload = messages.insert_query.payload or {}
    assert "created_at" not in payload
    assert "updated_at" not in payload


def test_a_conversation_the_caller_does_not_own_is_never_written() -> None:
    """No owned row means no insert at all: the store answers `None`."""
    store, _conversations, messages, _names = make_store(owned=None)

    assert store.create_for_user(USER_ID, CONVERSATION_ID, "Hello") is None
    assert messages.insert_query.payload is None


def test_a_foreign_conversation_matches_no_rows() -> None:
    """The owner filter is what makes a foreign conversation look nonexistent."""
    store, conversations, messages, _names = make_store(owned=None)

    store.create_for_user(OTHER_USER_ID, CONVERSATION_ID, "Hello")

    assert conversations.read.filters == [("id", CONVERSATION_ID), ("user_id", OTHER_USER_ID)]
    assert messages.insert_query.payload is None


@pytest.mark.parametrize("inserted_row", [None, {}])
def test_an_insert_without_a_confirmed_row_raises_a_store_error(
    inserted_row: dict[str, object] | None,
) -> None:
    """A write the database did not confirm becomes the store's own error."""
    store, _conversations, _messages, _names = make_store(inserted_row=inserted_row)

    with pytest.raises(MessageCreateError):
        store.create_for_user(USER_ID, CONVERSATION_ID, "Hello")


def test_the_created_row_is_parsed_into_the_domain_model() -> None:
    """The confirmed row is validated into a `Message`, not passed through."""
    store, _conversations, _messages, _names = make_store()

    message = store.create_for_user(USER_ID, CONVERSATION_ID, "Hello")

    assert isinstance(message, Message)
    assert message.content == "Hello"
    assert message.role == "user"
    assert str(message.conversation_id) == CONVERSATION_ID
    assert str(message.user_id) == USER_ID
