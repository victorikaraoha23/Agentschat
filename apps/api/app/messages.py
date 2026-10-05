"""Message domain type and store (Tasks 6.2 and 8.2).

Schema foundation plus the two writes the messaging endpoints need: a `user`
message a person sent, and the `assistant` message the runtime's reply becomes
after a successful execution. :class:`Message` mirrors the ``public.messages`` row
shape from ``supabase/migrations/0003_create_messages.sql`` (with its role check
widened by ``0004_allow_assistant_message_role.sql``) so code converts verified
rows into this model instead of passing untyped dicts.

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

# The roles the API writes. `user` comes from a person; `assistant` is the
# runtime's reply persisted after a successful execution (Task 8.2). The
# database's `messages_role_user_or_assistant` check refuses anything else --
# system, tool, function, and agent roles stay refused until a code path exists
# that can legitimately produce them.
MESSAGE_ROLE_USER = "user"
MESSAGE_ROLE_ASSISTANT = "assistant"


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
        """Append one ``user`` message to a conversation ``user_id`` owns, or `None`."""

    def create_assistant_for_user(
        self, user_id: str, conversation_id: str, content: str
    ) -> Message | None:
        """Append one ``assistant`` message to a conversation ``user_id`` owns, or `None`.

        Server-side only. No client can reach this path: the user-message request
        model has no role field, so a caller cannot ask for an assistant row. The
        execution flow calls it after a successful run and names the authenticated
        user itself, rather than trusting any identity the runtime returned.
        """


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
        """Append one ``user`` message to a conversation owned by ``user_id``.

        Returns the persisted row, or `None` when the caller does not own the
        conversation Ã¢â‚¬â€ the same answer for a foreign conversation and for one
        that does not exist.

        The conversation's `updated_at` is not written here: the migration's
        after-insert trigger refreshes it, so the timestamp stays correct no
        matter which path writes the message.
        """
        return self._insert_owned_message(
            user_id, conversation_id, content, MESSAGE_ROLE_USER
        )

    def create_assistant_for_user(
        self, user_id: str, conversation_id: str, content: str
    ) -> Message | None:
        """Append one ``assistant`` message to a conversation owned by ``user_id``.

        The author's id is the caller's verified identity, passed in by the
        execution flow. Nothing the agent runtime returned decides who owns this
        row, so a runtime that echoed back a different id, or none at all, cannot
        move the message to another user.

        The content is stored exactly as produced: no truncation, no reformatting,
        no appended metadata, and no Hermes text. The same after-insert trigger
        refreshes the conversation's `updated_at`, so a completed exchange marks
        the conversation as recently active without a second write.
        """
        return self._insert_owned_message(
            user_id, conversation_id, content, MESSAGE_ROLE_ASSISTANT
        )

    def _insert_owned_message(
        self, user_id: str, conversation_id: str, content: str, role: str
    ) -> Message | None:
        """Write one message of ``role`` after confirming the caller owns it.

        Shared by both public writes so the ownership check and the insert remain
        a single statement pair, with no second and looser path an assistant row
        could take. ``role`` is a module constant chosen by the caller above,
        never a value arriving in a request body.
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
                    "role": role,
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
