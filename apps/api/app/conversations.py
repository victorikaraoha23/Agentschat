"""Conversation domain type and store (Tasks 5.1–5.3).

Schema-only foundation plus the reads and the single write the conversation
endpoints need. :class:`Conversation` mirrors the ``public.conversations`` row
shape from ``supabase/migrations/0002_create_conversations.sql`` so code
converts verified rows into this model instead of passing untyped dicts.
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
# no query can widen the conversation contract by accident.
CONVERSATION_COLUMNS: tuple[str, ...] = (
    "id",
    "user_id",
    "title",
    "created_at",
    "updated_at",
)


class Conversation(BaseModel):
    """A conversation row: database-generated id, one owner, nullable title."""

    id: UUID
    user_id: UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class ConversationResultLike(Protocol):
    """What the executed insert hands back.

    With the row's columns selected, ``.single()`` resolves to one row object,
    so the only acceptable payload is a parsed row mapping.
    """

    data: dict[str, object] | None


class ConversationInsertQueryLike(Protocol):
    """The insert chain this module runs: select the row back, then execute."""

    def select(self, *columns: str) -> ConversationInsertQueryLike:
        """Choose the columns the insert returns."""

    def single(self) -> ConversationInsertQueryLike:
        """Require exactly one row back instead of a list."""

    def execute(self) -> ConversationResultLike | None:
        """Run the insert against Supabase."""


class ConversationRowsResultLike(Protocol):
    """What an executed rows read hands back: zero or more row mappings."""

    data: list[dict[str, object]] | None


class ConversationRowResultLike(Protocol):
    """What an executed at-most-one-row read hands back: one mapping or nothing.

    ``maybe_single()`` resolves to ``None`` rather than an empty payload when the
    query matches no row, so a row that does not exist and a row owned by
    someone else are the same observation here.
    """

    data: dict[str, object] | None


class ConversationMaybeSingleQueryLike(Protocol):
    """The tail of a one-row read, after ``maybe_single()`` has been applied."""

    def execute(self) -> ConversationRowResultLike | None:
        """Run the query against Supabase, accepting zero rows."""


class ConversationSelectQueryLike(Protocol):
    """The read chain both lookups build: columns, owner filter, then execute.

    Filters are applied before :meth:`maybe_single`, mirroring the SDK: the
    at-most-one-row builder that follows exposes no filter methods of its own.
    """

    def eq(self, column: str, value: object) -> ConversationSelectQueryLike:
        """Filter the query to one column value."""

    def order(self, column: str, *, desc: bool = False) -> ConversationSelectQueryLike:
        """Order the result rows by one column."""

    def maybe_single(self) -> ConversationMaybeSingleQueryLike:
        """Accept zero or one row instead of failing on an empty result."""

    def execute(self) -> ConversationRowsResultLike | None:
        """Run the rows query against Supabase."""


class ConversationTableLike(Protocol):
    """The table handle this module reads and writes through."""

    def insert(self, payload: dict[str, object]) -> ConversationInsertQueryLike:
        """Start an insert of one row payload."""

    def select(self, *columns: str) -> ConversationSelectQueryLike:
        """Start a column-scoped read of the table."""


class ConversationClientLike(Protocol):
    """The Supabase client surface this module uses."""

    def table(self, name: str) -> ConversationTableLike:
        """Return the handle for one table."""


class ConversationStore(Protocol):
    """How the conversation endpoints read and write rows — the seam tests replace."""

    def create(self, user_id: str, title: str | None) -> Conversation:
        """Insert one row owned by ``user_id`` and return the created record."""

    def list_for_user(self, user_id: str) -> list[Conversation]:
        """Return ``user_id``'s conversations in the documented order."""

    def get_for_user(self, user_id: str, conversation_id: str) -> Conversation | None:
        """Return one conversation owned by ``user_id``, or `None` when there is none."""


class ConversationCreateError(Exception):
    """The insert did not return a usable created row."""


class SupabaseConversationStore:
    """Read and write ``public.conversations`` through the backend Supabase client.

    Runs server-side with the service-role key, which bypasses Row Level
    Security — so the RLS policies are *not* what protects these statements.
    What protects them is that every statement is scoped to the identity the
    endpoint's Task 3.2 dependency already verified: a write names exactly that
    identity as ``user_id``, and a read filters on it. A row owned by someone
    else is therefore filtered out by the query itself, which is why it is
    indistinguishable from a row that does not exist.
    """

    def __init__(
        self,
        settings: Settings,
        client_factory: Callable[[Settings], ConversationClientLike] = get_supabase_client,
    ) -> None:
        """Retain settings and a client factory for use when a query is requested."""
        self._settings = settings
        self._client_factory = client_factory

    def create(self, user_id: str, title: str | None) -> Conversation:
        """Insert ``(user_id, title)`` and return the created row as a model."""
        client = self._client_factory(self._settings)
        result = (
            client.table("conversations")
            .insert({"user_id": user_id, "title": title})
            .select(*CONVERSATION_COLUMNS)
            .single()
            .execute()
        )
        if result is None or result.data is None:
            raise ConversationCreateError("The conversation could not be created.")
        return Conversation.model_validate(result.data)

    def list_for_user(self, user_id: str) -> list[Conversation]:
        """Read ``user_id``'s rows, newest first, with a deterministic tiebreak.

        The owner filter is what makes this read safe, and the database — not
        this process — does the filtering, so no other user's row is ever loaded.
        """
        client = self._client_factory(self._settings)
        result = (
            client.table("conversations")
            .select(*CONVERSATION_COLUMNS)
            .eq("user_id", user_id)
            # `updated_at` alone is not a total order: rows written in the same
            # instant compare equal, so the id breaks every remaining tie and the
            # same data always comes back in the same sequence.
            .order("updated_at", desc=True)
            .order("id", desc=True)
            .execute()
        )
        if result is None or result.data is None:
            return []
        return [Conversation.model_validate(row) for row in result.data]

    def get_for_user(self, user_id: str, conversation_id: str) -> Conversation | None:
        """Read one row owned by ``user_id``, or `None` for anything else.

        The id and the owner are filtered in the same query, so a conversation
        that belongs to someone else returns exactly what a nonexistent one
        returns: no row at all.
        """
        client = self._client_factory(self._settings)
        result = (
            client.table("conversations")
            .select(*CONVERSATION_COLUMNS)
            .eq("id", conversation_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        if result is None or result.data is None:
            return None
        return Conversation.model_validate(result.data)
