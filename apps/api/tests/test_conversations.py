"""Conversation schema: migration structure, domain type, and RLS intent (Task 5.1).

These tests assert the migration file in the repository (not a remote schema)
plus the minimal backend domain type. RLS behavior itself cannot run here —
there is no live Postgres — so it is verified by reading the policy text, the
strongest deterministic check available without a database. The one exception
is the route-surface check, which guards that Tasks 5.2–5.3 added conversation
creation and retrieval and nothing beyond them.
"""

from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from app.conversations import Conversation
from app.main import app

MIGRATION = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "supabase"
    / "migrations"
    / "0002_create_conversations.sql"
)


@pytest.fixture(scope="module")
def sql() -> str:
    """Read the migration once for the structural assertions below."""
    return MIGRATION.read_text(encoding="utf-8")


def test_migration_file_exists() -> None:
    """The migration is a versioned file the repository can review and reapply."""
    assert MIGRATION.is_file()


def test_conversations_table_with_uuid_primary_key(sql: str) -> None:
    """The table exists with a database-generated UUID primary key."""
    assert "create table public.conversations (" in sql
    assert "id uuid primary key default gen_random_uuid()" in sql


def test_user_id_enforces_single_owner(sql: str) -> None:
    """Ownership is non-null, references the profile identity, cascades on delete."""
    assert "user_id uuid not null references public.profiles (id) on delete cascade" in sql


def test_title_is_nullable_without_default(sql: str) -> None:
    """No title is invented at creation time; a later task assigns titles."""
    assert "title text," in sql
    assert "title text not null" not in sql
    assert "title text default" not in sql


def test_timestamps_are_database_managed(sql: str) -> None:
    """Creation/modification times come from the database, not the application."""
    assert "created_at timestamptz not null default now()" in sql
    assert "updated_at timestamptz not null default now()" in sql
    assert "conversations_set_updated_at" in sql
    assert "before update on public.conversations" in sql


def test_owner_index_exists_and_nothing_speculative(sql: str) -> None:
    """The one real query pattern (this user's rows) is indexed; nothing else is."""
    assert "create index conversations_user_id_idx on public.conversations (user_id)" in sql
    assert sql.lower().count("create index") == 1


def test_rls_is_enabled(sql: str) -> None:
    """Row Level Security is turned on for the table."""
    assert "alter table public.conversations enable row level security" in sql


def test_select_policy_reads_only_own_rows(sql: str) -> None:
    """SELECT is limited to rows whose owner is the caller."""
    assert 'create policy "conversations_select_own"' in sql
    assert "for select" in sql
    assert "to authenticated" in sql
    assert "using (auth.uid() = user_id)" in sql


def test_insert_policy_forbids_forged_ownership(sql: str) -> None:
    """INSERT carries a WITH CHECK so a client-supplied user_id cannot name another user."""
    assert 'create policy "conversations_insert_own"' in sql
    assert "for insert" in sql
    assert "with check (auth.uid() = user_id)" in sql


def test_update_policy_locks_both_sides(sql: str) -> None:
    """UPDATE gates the existing row and the proposed new row on the caller."""
    assert 'create policy "conversations_update_own"' in sql
    assert "for update" in sql
    assert "using (auth.uid() = user_id)" in sql
    assert "with check (auth.uid() = user_id)" in sql


def test_delete_policy_removes_only_own_rows(sql: str) -> None:
    """DELETE is limited to rows whose owner is the caller."""
    assert 'create policy "conversations_delete_own"' in sql
    assert "for delete" in sql
    assert "using (auth.uid() = user_id)" in sql


def test_no_broad_policy_grants_all_access(sql: str) -> None:
    """No policy opens the table beyond per-owner rows; anon gets nothing."""
    assert "to anon" not in sql
    assert "using (true)" not in sql
    assert "with check (true)" not in sql
    assert sql.count("create policy") == 4


def test_conversation_model_parses_a_row() -> None:
    """The domain type carries exactly the row fields with typed shapes."""
    conversation = Conversation.model_validate(
        {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "user_id": "123e4567-e89b-12d3-a456-426614174000",
            "title": None,
            "created_at": "2026-10-03T12:00:00Z",
            "updated_at": "2026-10-03T12:00:00Z",
        }
    )

    assert conversation.title is None
    assert str(conversation.id) == "123e4567-e89b-12d3-a456-426614174000"
    assert conversation.user_id == UUID("123e4567-e89b-12d3-a456-426614174000")


def test_conversation_model_rejects_malformed_rows() -> None:
    """Malformed ids fail validation rather than flowing onward."""
    with pytest.raises(ValidationError):
        Conversation.model_validate(
            {
                "id": "not-a-uuid",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "title": None,
                "created_at": "2026-10-03T12:00:00Z",
                "updated_at": "2026-10-03T12:00:00Z",
            }
        )


def test_conversation_surface_is_creation_and_retrieval_only() -> None:
    """The collection is POST + GET, plus one GET by id — no other verb yet."""
    routes = {
        (route.path, method)
        for route in app.routes
        if hasattr(route, "path") and hasattr(route, "methods")
        for method in route.methods
    }

    assert "/health" in {path for path, _ in routes}
    assert "/me" in {path for path, _ in routes}
    assert ("/conversations", "POST") in routes
    assert ("/conversations", "GET") in routes
    assert ("/conversations/{conversation_id}", "GET") in routes
    assert sorted(method for path, method in routes if path == "/conversations") == [
        "GET",
        "POST",
    ]
    assert [
        method for path, method in routes if path == "/conversations/{conversation_id}"
    ] == ["GET"]
    # Task 5.4 owns modification and deletion; nothing may appear here early.
    assert not {method for _, method in routes} & {"PATCH", "PUT", "DELETE"}
    assert not any(path.startswith("/chats") for path, _ in routes)


def test_app_starts_with_conversation_module_importable() -> None:
    """The domain type imports cleanly and the app still serves its routes."""
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
