"""Application-level user profile: the AgentsChat record behind a Supabase identity (Task 3.3).

Supabase Auth stays the source of truth for authentication. This module is the
identity bridge: given a verified :class:`~app.auth.AuthenticatedUser`, it
loads the one ``public.profiles`` row keyed by that identity's ``user_id`` —
which the database guarantees equals an ``auth.users.id``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from pydantic import BaseModel

from app.config import Settings
from app.supabase_client import get_supabase_client


class UserProfile(BaseModel):
    """The minimal profile representation returned to the caller."""

    user_id: str
    created_at: datetime
    updated_at: datetime


class ProfileRowLike(Protocol):
    """The ``profiles`` fields this module reads."""

    id: str
    created_at: datetime
    updated_at: datetime


class ProfileRow(BaseModel):
    """Typed profile fields parsed from the SDK's JSON row data."""

    id: str
    created_at: datetime
    updated_at: datetime


class ProfileRowNotFoundError(Exception):
    """No profile row exists for the verified identity (trigger lag or drift)."""


class ProfileQueryLike(Protocol):
    """The single-row query chain this module runs."""

    def eq(self, column: object, value: object) -> ProfileQueryLike:
        """Filter the query to one column value."""

    def maybe_single(self) -> ProfileQueryLike:
        """Accept zero or one row instead of failing on an empty result."""

    def execute(self) -> ProfileResultLike | None:
        """Run the query against Supabase."""


class ProfileResultLike(Protocol):
    """What the executed single-row query hands back."""

    data: ProfileRowLike | dict[str, object] | None


class ProfileTableLike(Protocol):
    """The table handle this module queries."""

    def select(self, *columns: str) -> ProfileQueryLike:
        """Start a column-scoped read of the table."""


class ProfileClientLike(Protocol):
    """The Supabase client surface this module uses."""

    def table(self, name: str) -> ProfileTableLike:
        """Return the handle for one table."""


class ProfileStore(Protocol):
    """How the profile lookup obtains a row — the seam tests replace."""

    def get_by_id(self, user_id: str) -> ProfileRowLike | None:
        """Return the profile row for ``user_id``, or `None` when absent."""


class SupabaseProfileStore:
    """Read ``public.profiles`` through the backend Supabase client.

    Runs server-side with the service-role key, so the RLS `select` policy is
    not what protects this read — the dependency requires a verified identity
    first, and the lookup is then scoped to exactly that identity's row.
    """

    def __init__(
        self,
        settings: Settings,
        client_factory: Callable[[Settings], ProfileClientLike] = get_supabase_client,
    ) -> None:
        """Retain settings and a client factory for use when a lookup is requested."""
        self._settings = settings
        self._client_factory = client_factory

    def get_by_id(self, user_id: str) -> ProfileRowLike | None:
        """Run `select … where id = :user_id`, accepting zero or one row."""
        client = self._client_factory(self._settings)
        result = (
            client.table("profiles")
            .select("id", "created_at", "updated_at")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        if result is None or result.data is None:
            return None
        if isinstance(result.data, dict):
            return ProfileRow.model_validate(result.data)
        return result.data



def to_user_profile(row: ProfileRowLike) -> UserProfile:
    """Convert a verified profile row into the outward-facing model."""
    return UserProfile(user_id=row.id, created_at=row.created_at, updated_at=row.updated_at)


def load_user_profile(user_id: str, store: ProfileStore) -> UserProfile:
    """Resolve the profile for a verified identity, or say it is missing.

    The caller supplies a ``user_id`` that :mod:`app.auth` already verified —
    this module never accepts an identity from the client directly.
    """
    row = store.get_by_id(user_id)
    if row is None:
        raise ProfileRowNotFoundError(
            f"No profile exists for the authenticated identity {user_id!r}."
        )
    return to_user_profile(row)
