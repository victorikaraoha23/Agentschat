"""Conversation domain type and creation store (Tasks 5.1–5.2).

Schema-only foundation plus the single write the creation endpoint needs.
:class:`Conversation` mirrors the ``public.conversations`` row shape from
``supabase/migrations/0002_create_conversations.sql`` so code converts
verified rows into this model instead of passing untyped dicts.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel

from app.config import Settings
from app.supabase_client import get_supabase_client


class Conversation(BaseModel):
    """A conversation row: database-generated id, one owner, nullable title."""

    id: UUID
    user_id: str
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


class ConversationTableLike(Protocol):
    """The table handle this module inserts through."""

    def insert(self, payload: dict[str, object]) -> ConversationInsertQueryLike:
        """Start an insert of one row payload."""


class ConversationClientLike(Protocol):
    """The Supabase client surface this module uses."""

    def table(self, name: str) -> ConversationTableLike:
        """Return the handle for one table."""


class ConversationStore(Protocol):
    """How the creation endpoint persists a row — the seam tests replace."""

    def create(self, user_id: str, title: str | None) -> Conversation:
        """Insert one row owned by ``user_id`` and return the created record."""


class ConversationCreateError(Exception):
    """The insert did not return a usable created row."""


class SupabaseConversationStore:
    """Insert into ``public.conversations`` through the backend Supabase client.

    Runs server-side with the service-role key, so the RLS ``insert`` policy
    is not what protects this write — the endpoint passes an identity its
    Task 3.2 dependency already verified, and the payload names exactly that
    identity as ``user_id``. The database policy remains the final boundary.
    """

    def __init__(
        self,
        settings: Settings,
        client_factory: Callable[[Settings], ConversationClientLike] = get_supabase_client,
    ) -> None:
        """Retain settings and a client factory for use when a write is requested."""
        self._settings = settings
        self._client_factory = client_factory

    def create(self, user_id: str, title: str | None) -> Conversation:
        """Insert ``(user_id, title)`` and return the created row as a model."""
        client = self._client_factory(self._settings)
        result = (
            client.table("conversations")
            .insert({"user_id": user_id, "title": title})
            .select("id", "user_id", "title", "created_at", "updated_at")
            .single()
            .execute()
        )
        if result is None or result.data is None:
            raise ConversationCreateError("The conversation could not be created.")
        return Conversation.model_validate(result.data)

