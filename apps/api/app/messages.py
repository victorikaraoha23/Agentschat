"""Message domain type and store (Task 6.2).

Schema foundation plus the one write the first messaging endpoint needs.
:class:`Message` mirrors the ``public.messages`` row shape from
``supabase/migrations/0003_create_messages.sql`` so code converts verified rows
into this model instead of passing untyped dicts.

Ownership is enforced in the store, in the same statement, exactly as the
conversation store does (Tasks 5.2Ã¢â‚¬â€œ5.4): the conversation is read with the
caller's verified ``user_id`` alongside its id before anything is inserted, so a
conversation owned by someone else is indistinguishable from one that does not
exist Ã¢â‚¬â€ the endpoint answers the same 404 for both. The database's RLS policies
remain the security boundary for any client that talks to PostgREST directly;
this backend uses the service-role client, which bypasses RLS, so the query
scoping here is what protects these statements.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel

from app.config import Settings
from app.supabase_client import get_supabase_client

# The row fields the API exposes. Named once and selected by every statement, so
# no query can widen the message contract by accident.
MESSAGE_COLUMNS: tuple[str, ...] = (
    "id",
    "conversation_id",
    "user_id",
    "role",
    "content",
    "created_at",
)

# The only role this task writes. Assistant, system, and tool roles arrive with
# the agent tasks; the column's check constraint refuses anything else until the
# migration that widens it exists.
MESSAGE_ROLE_USER = "user"


class Message(BaseModel):
    """A message row: database-generated id, one conversation, one author."""

    id: UUID
    conversation_id: UUID
    user_id: UUID
    role: str
    content: str
    created_at: datetime


class MessageResultLike(Protocol):
    """What an executed insert hands back.

    With the row's columns selected, ``.single()`` resolves to one row object,
    so the only acceptable payload is a parsed row mapping.
    """

    data: dict[str, object] | None


class MessageInsertQueryLike(Protocol):
    """The insert chain this module runs: select the row back, then execute."""

    def select(self, *columns: str) -> MessageInsertQueryLike:
        """Choose the columns the insert returns."""

    def single(self) -> MessageInsertQueryLike:
        """Require exactly one row back instead of a list."""

    def execute(self) -> MessageResultLike | None:
        """Run the insert against Supabase."""


class MessageRowResultLike(Protocol):
    """What an executed at-most-one-row read hands back: one mapping or nothing.

    ``maybe_single()`` resolves to ``None`` rather than an empty payload when the
    query matches no row, so a conversation that does not exist and one owned by
    someone else are the same observation here.
    """

    data: dict[str, object] | None


class MessageMaybeSingleQueryLike(Protocol):
    """The tail of a one-row read, after ``maybe_single()`` has been applied."""

    def execute(self) -> MessageRowResultLike | None:
        """Run the query against Supabase, accepting zero rows."""


class MessageSelectQueryLike(Protocol):
    """The ownership-check chain: columns, id filter, owner filter, execute.

    Filters are applied before :meth:`maybe_single`, mirroring the SDK: the
    at-most-one-row builder that follows exposes no filter methods of its own.
    """

    def eq(self, column: str, value: object) -> MessageSelectQueryLike:
        """Filter the query to one column value."""

    def maybe_single(self) -> MessageMaybeSingleQueryLike:
        """Accept zero or one row instead of failing on an empty result."""

    def execute(self) -> MessageRowResultLike | None:
        """Run the query against Supabase, accepting zero rows."""


class MessageTableLike(Protocol):
    """The table handle this module reads and writes through.

    The same handle shape serves both tables the store touches: the ownership
    check reads ``conversations``, and the insert writes ``messages``.
    """

    def insert(self, payload: dict[str, object]) -> MessageInsertQueryLike:
        """Start an insert of one row payload."""



    def select(self, *columns: str) -> MessageSelectQueryLike:
        """Start a column-scoped read of the table."""


class MessageClientLike(Protocol):
    """The Supabase client surface this module uses."""

    def table(self, name: str) -> MessageTableLike:
        """Return the handle for one table."""


class MessageStore(Protocol):
    """How the message endpoint writes rows Ã¢â‚¬â€ the seam tests replace."""

    def create_for_user(
        self, user_id: str, conversation_id: str, content: str
    ) -> Message | None:
        """Append one message to a conversation ``user_id`` owns, or `None`."""


class MessageCreateError(Exception):
    """The insert did not return a usable created row."""



class SupabaseMessageStore:
    """Write ``public.messages`` through the backend Supabase client.

    Runs server-side with the service-role key, which bypasses Row Level
    Security Ã¢â‚¬â€ so the RLS policies are *not* what protects these statements.
    What protects them is that the conversation is read with the identity the
    endpoint's Task 3.2 dependency already verified, and that the inserted row
    names exactly that identity as its author. A conversation belonging to
    someone else therefore never reaches the insert at all.
    """

    def __init__(
        self,
        settings: Settings,
        client_factory: Callable[[Settings], MessageClientLike] = get_supabase_client,
    ) -> None:
        """Retain settings and a client factory for use when a query is requested."""
        self._settings = settings
        self._client_factory = client_factory

    def create_for_user(
        self, user_id: str, conversation_id: str, content: str
    ) -> Message | None:
        """Append one message to a conversation owned by ``user_id``.

        Returns the persisted row, or `None` when the caller does not own the
        conversation Ã¢â‚¬â€ the same answer for a foreign conversation and for one
        that does not exist.

        The conversation's `updated_at` is not written here: the migration's
        after-insert trigger refreshes it, so the timestamp stays correct no
        matter which path writes the message.
        """
        client = self._client_factory(self._settings)
        owned = (
            client.table("conversations")
            .select("id")
            .eq("id", conversation_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        if owned is None or owned.data is None:
            return None

        result = (
            client.table("messages")
            .insert(
                {
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "role": MESSAGE_ROLE_USER,
                    "content": content,
                }
            )
            .select(*MESSAGE_COLUMNS)
            .single()
            .execute()
        )
        if result is None or not result.data:
            raise MessageCreateError("The message could not be created.")
        return Message.model_validate(result.data)
