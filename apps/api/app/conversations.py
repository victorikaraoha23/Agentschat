"""Conversation domain type: the persistent record behind a user's chat (Task 5.1).

Schema-only foundation — no endpoints, no repository, no service layer. This
module keeps the API layer type-safe for the later task that implements
conversation creation: it mirrors the `public.conversations` row shape from
`supabase/migrations/0002_create_conversations.sql` so future code converts
verified rows into this model instead of passing untyped dicts.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class Conversation(BaseModel):
    """A conversation row: database-generated id, one owner, nullable title."""

    id: UUID
    user_id: str
    title: str | None
    created_at: datetime
    updated_at: datetime
