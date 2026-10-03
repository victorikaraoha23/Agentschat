"""User profile: schema bridge, store lookup, and /me (Task 3.3).

The database is faked through the module's seams, so no test needs a live
Supabase project or credentials. SQL structure is asserted from the migration
file in the repository, not from a remote schema.
"""

from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from supabase import PostgrestAPIError, SupabaseException

from app.auth import AuthenticatedUser, get_access_token_verifier
from app.main import app
from app.profiles import (
    ProfileRowNotFoundError,
    SupabaseProfileStore,
    UserProfile,
    load_user_profile,
    to_user_profile,
)
from app.supabase_client import SupabaseNotConfiguredError

USER_ID = "123e4567-e89b-12d3-a456-426614174000"
OTHER_USER_ID = "123e4567-e89b-12d3-a456-426614174999"
CREATED = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
UPDATED = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)


class FakeRow:
    """The `profiles` fields the module reads."""

    def __init__(self, id: str, created_at: datetime, updated_at: datetime) -> None:
        """Build a row with explicit identity and timestamps for profile assertions."""
        self.id = id
        self.created_at = created_at
        self.updated_at = updated_at


class FakeStore:
    """Stand-in for the profile store."""

    def __init__(self, rows: dict[str, FakeRow]) -> None:
        """Seed identity-keyed rows and start an empty lookup history."""
        self._rows = rows
        self.requested_ids: list[str] = []

    def get_by_id(self, user_id: str) -> FakeRow | None:
        """Record the requested identity and return its seeded row, if present."""
        self.requested_ids.append(user_id)
        return self._rows.get(user_id)


class FakeResult:
    """What the executed query hands back."""

    def __init__(self, row: FakeRow | None) -> None:
        """Expose a prepared row or missing result through the query's data field."""
        self.data = row


class FakeTableHandle:
    """The part of the table handle this test observes (columns, filters)."""

    def __init__(self) -> None:
        """Initialize query observations used to assert column and identity scoping."""
        self.selected: tuple[str, ...] = ()
        self.filters: list[tuple[object, object]] = []


class FakeQuery:
    """Query chain: records the column filter, returns the prepared row."""

    def __init__(self, row: FakeRow | None, table: FakeTableHandle) -> None:
        """Bind a prepared result to the table's shared query observations."""
        self._row = row
        self._table = table

    def eq(self, column: object, value: object):  # type: ignore[no-untyped-def]
        """Record an equality filter without applying it to the prepared row."""
        self._table.filters.append((column, value))
        return self

    def maybe_single(self):  # type: ignore[no-untyped-def]
        """Preserve chaining for a fake result already limited to zero or one row."""
        return self

    def execute(self) -> FakeResult:
        """Return the prepared query result without contacting Supabase."""
        return FakeResult(self._row)


class FakeTable:
    """Stand-in for the `profiles` table handle."""

    def __init__(self, row: FakeRow | None) -> None:
        """Prepare a table result and fresh observations for its query chain."""
        self._row = row
        self.observed = FakeTableHandle()

    def select(self, *columns: str):  # type: ignore[no-untyped-def]
        """Record selected columns and start a query returning the prepared row."""
        self.observed.selected = columns
        return FakeQuery(self._row, self.observed)


class FakeClient:
    """Stand-in for the Supabase client."""

    def __init__(self, row: FakeRow | None) -> None:
        """Seed a result for table requests and track the handles they create."""
        self._row = row
        self.tables: dict[str, FakeTable] = {}

    def table(self, name: str) -> FakeTable:
        """Create and record a named table handle backed by the seeded result."""
        handle = FakeTable(self._row)
        self.tables[name] = handle
        return handle


def fake_settings(*, configured: bool = True):  # type: ignore[no-untyped-def]
    """Settings stand-in carrying only what the store reads."""
    from types import SimpleNamespace

    return SimpleNamespace(
        supabase_url="https://example.supabase.co" if configured else None,
        supabase_service_role_key="test-service-role-key" if configured else None,
    )


class FakeVerifier:
    """Stand-in for the token verifier: accepts one bearer token."""

    def __init__(self, user_id: str) -> None:
        """Choose the identity returned when the expected test token is verified."""
        self._user_id = user_id

    def verify(self, access_token: str) -> AuthenticatedUser:
        """Assert the expected bearer token and return the configured test identity."""
        assert access_token == "header.payload.signature"
        return AuthenticatedUser(user_id=self._user_id, email="person@example.com")


def read_migration() -> str:
    """Load the migration text from the repository (apps/api/tests → root)."""
    from pathlib import Path

    return (
        Path(__file__).resolve().parent.parent.parent.parent
        / "supabase"
        / "migrations"
        / "0001_create_profiles.sql"
    ).read_text(encoding="utf-8")


def test_migration_creates_profiles_keyed_by_auth_users() -> None:
    """The table's id is the Auth identity: uuid PK with an auth.users foreign key."""
    sql = read_migration().lower()

    assert "create table public.profiles" in sql
    assert "id uuid primary key references auth.users (id)" in sql
    assert "on delete cascade" in sql
    assert "created_at timestamptz not null default now()" in sql
    assert "updated_at timestamptz not null default now()" in sql


def test_migration_rejects_arbitrary_uuids_by_relationship() -> None:
    """No second identity exists: the id column is the reference, not a plain uuid."""
    sql = read_migration().lower()

    assert "references auth.users" in sql
    # A separately generated identity (gen_random_uuid default, serial, second
    # id column) would let a profile exist for no Auth user.
    assert "gen_random_uuid" not in sql
    assert sql.count("uuid") >= 1


def test_migration_enables_rls_with_only_an_owner_read_policy() -> None:
    """RLS is on, the select policy matches only the caller's row, and writes stay closed."""
    sql = read_migration().lower()

    assert "alter table public.profiles enable row level security" in sql
    assert "create policy" in sql
    assert "for select" in sql
    assert "auth.uid() = id" in sql
    assert "for update" not in sql
    assert "for delete" not in sql
    assert "for insert" not in sql
    assert "to authenticated" in sql


def test_migration_creates_the_profile_from_the_auth_identity() -> None:
    """A trigger on auth.users inserts one row, idempotently; writes need no grants."""
    sql = read_migration().lower()

    assert "after insert on auth.users" in sql
    assert "insert into public.profiles (id)" in sql
    assert "on conflict (id) do nothing" in sql
    assert "security definer" in sql


def test_load_user_profile_returns_the_verified_identity_row() -> None:
    """The lookup resolves exactly the row for the verified identity."""
    store = FakeStore({USER_ID: FakeRow(USER_ID, CREATED, UPDATED)})

    profile = load_user_profile(USER_ID, store)

    assert profile == UserProfile(user_id=USER_ID, created_at=CREATED, updated_at=UPDATED)
    assert store.requested_ids == [USER_ID]


def test_load_user_profile_is_missing_without_a_row() -> None:
    """A verified identity with no row raises — never an invented profile."""
    store = FakeStore({})

    with pytest.raises(ProfileRowNotFoundError):
        load_user_profile(USER_ID, store)


def test_supabase_store_queries_exactly_one_scoped_row() -> None:
    """The store reads only the three profile columns, filtered to one id."""
    row = FakeRow(USER_ID, CREATED, UPDATED)
    client = FakeClient(row)
    store = SupabaseProfileStore(fake_settings(), client_factory=lambda _: client)

    assert store.get_by_id(USER_ID) is row

    handle = client.tables["profiles"]
    assert handle.observed.selected == ("id", "created_at", "updated_at")
    assert handle.observed.filters == [("id", USER_ID)]


@pytest.mark.parametrize("result", [None, FakeResult(None)])
def test_supabase_store_accepts_missing_results(
    result: FakeResult | None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both an absent SDK response and absent row data mean no profile."""
    monkeypatch.setattr(FakeQuery, "execute", lambda self: result)
    store = SupabaseProfileStore(fake_settings(), client_factory=lambda _: FakeClient(None))

    assert store.get_by_id(USER_ID) is None
    with pytest.raises(ProfileRowNotFoundError):
        load_user_profile(USER_ID, store)


def test_me_reads_dictionary_row_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """A real SDK response carries JSON fields, including timestamp strings."""
    from postgrest.base_request_builder import SingleAPIResponse
    import app.main as main_module

    result = SingleAPIResponse(data={
        "id": USER_ID,
        "created_at": CREATED.isoformat(),
        "updated_at": UPDATED.isoformat(),
    })
    monkeypatch.setattr(FakeQuery, "execute", lambda self: result)
    store = SupabaseProfileStore(fake_settings(), client_factory=lambda _: FakeClient(None))
    monkeypatch.setitem(
        app.dependency_overrides, get_access_token_verifier, lambda: FakeVerifier(USER_ID),
    )
    monkeypatch.setattr(main_module, "SupabaseProfileStore", lambda settings: store)

    response = TestClient(app).get(
        "/me", headers={"Authorization": "Bearer header.payload.signature"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": USER_ID,
        "created_at": "2026-10-01T12:00:00Z",
        "updated_at": "2026-10-02T12:00:00Z",
    }


@pytest.mark.parametrize("failure", [
    PostgrestAPIError({"message": "private provider detail", "code": "XX000"}),
    SupabaseException("private provider detail"),
    SupabaseNotConfiguredError("private provider detail"),
    httpx.ConnectError("private provider detail"),
    httpx.ReadTimeout("private provider detail"),
])
def test_me_maps_profile_store_failures_to_503(
    failure: Exception, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    """A store failure after authentication has a safe, documented response."""
    import app.main as main_module

    def fail_query(self: FakeQuery) -> FakeResult:
        raise failure

    monkeypatch.setattr(FakeQuery, "execute", fail_query)
    store = SupabaseProfileStore(fake_settings(), client_factory=lambda _: FakeClient(None))
    monkeypatch.setitem(
        app.dependency_overrides, get_access_token_verifier, lambda: FakeVerifier(USER_ID),
    )
    monkeypatch.setattr(main_module, "SupabaseProfileStore", lambda settings: store)

    response = TestClient(app, raise_server_exceptions=False).get(
        "/me", headers={"Authorization": "Bearer header.payload.signature"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication is temporarily unavailable."}
    assert "private provider detail" not in caplog.text


def test_to_user_profile_carries_only_profile_fields() -> None:
    """The outward model holds no credential, token, or database internals."""
    profile = to_user_profile(FakeRow(USER_ID, CREATED, UPDATED))

    assert profile.model_dump() == {
        "user_id": USER_ID,
        "created_at": CREATED,
        "updated_at": UPDATED,
    }


def test_me_rejects_unauthenticated_requests() -> None:
    """No bearer token means the 401 authentication error, never a profile."""
    previous = dict(app.dependency_overrides)
    try:
        response = TestClient(app).get("/me")
    finally:
        app.dependency_overrides = previous

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


def test_me_returns_only_the_caller_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    """An authenticated caller resolves exactly their own row — never another's."""
    import app.main as main_module

    store = FakeStore(
        {
            USER_ID: FakeRow(USER_ID, CREATED, UPDATED),
            OTHER_USER_ID: FakeRow(OTHER_USER_ID, CREATED, UPDATED),
        }
    )
    monkeypatch.setitem(
        app.dependency_overrides,
        get_access_token_verifier,
        lambda: FakeVerifier(USER_ID),
    )
    monkeypatch.setattr(
        main_module, "SupabaseProfileStore", lambda settings: store
    )
    try:
        response = TestClient(app).get(
            "/me", headers={"Authorization": "Bearer header.payload.signature"}
        )
    finally:
        app.dependency_overrides = {}

    assert response.status_code == 200
    assert response.json() == {
        "user_id": USER_ID,
        "created_at": "2026-10-01T12:00:00Z",
        "updated_at": "2026-10-02T12:00:00Z",
    }
    assert store.requested_ids == [USER_ID]


def test_me_refuses_to_leak_probe_results_for_a_missing_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A verified identity with no row is a 500 with a fixed message, not a 404."""
    import app.main as main_module

    monkeypatch.setitem(
        app.dependency_overrides,
        get_access_token_verifier,
        lambda: FakeVerifier(OTHER_USER_ID),
    )
    monkeypatch.setattr(
        main_module, "SupabaseProfileStore", lambda settings: FakeStore({})
    )
    try:
        response = TestClient(app).get(
            "/me", headers={"Authorization": "Bearer header.payload.signature"}
        )
    finally:
        app.dependency_overrides = {}

    assert response.status_code == 500
    assert response.json() == {"detail": "The authenticated profile is unavailable."}
    assert OTHER_USER_ID not in response.text


