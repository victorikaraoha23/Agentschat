"""Message schema: migration structure, domain type, and RLS intent (Task 6.2).

These tests assert the migration file in the repository (not a remote schema)
plus the backend domain type. RLS behavior itself cannot run here — there is no
live Postgres — so it is verified by reading the policy text, the strongest
deterministic check available without a database, exactly as Task 5.1's schema
tests do for conversations.
"""

from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.messages import MESSAGE_COLUMNS, MESSAGE_ROLE_USER, Message

MIGRATION = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "supabase"
    / "migrations"
    / "0003_create_messages.sql"
)

USER_ID = "123e4567-e89b-12d3-a456-426614174000"
CONVERSATION_ID = "223e4567-e89b-12d3-a456-426614174000"


@pytest.fixture(scope="module")
def sql() -> str:
    """Read the migration once for the structural assertions below."""
    return MIGRATION.read_text(encoding="utf-8")


def test_migration_file_exists() -> None:
    """The migration is a versioned file the repository can review and reapply."""
    assert MIGRATION.is_file()


def test_messages_table_with_uuid_primary_key(sql: str) -> None:
    """The table exists with a database-generated UUID primary key."""
    assert "create table public.messages (" in sql
    assert "id uuid primary key default gen_random_uuid()" in sql


def test_message_belongs_to_a_conversation(sql: str) -> None:
    """`conversation_id` is required and references the conversation table."""
    assert (
        "conversation_id uuid not null references public.conversations (id) on delete cascade"
        in sql
    )


def test_author_enforces_single_owner(sql: str) -> None:
    """The author is non-null and references the profile identity, cascading."""
    assert "user_id uuid not null references public.profiles (id) on delete cascade" in sql


def test_role_is_constrained_to_user(sql: str) -> None:
    """Only `user` is allowed now; the constraint, not the application, holds it."""
    assert "role text not null," in sql
    assert "constraint messages_role_user_only check (role = 'user')" in sql
    # No default may quietly invent a role for a writer that omits it.
    assert "role text not null default" not in sql


def test_content_is_required_and_not_blank(sql: str) -> None:
    """Content is plain text, required, and the database refuses a blank one."""
    assert "content text not null," in sql
    assert "constraint messages_content_not_blank check (char_length(btrim(content)) > 0)" in sql


def test_created_at_is_database_managed(sql: str) -> None:
    """The creation time comes from the database; the application writes none."""
    assert "created_at timestamptz not null default now()" in sql
    # A message has no `updated_at`: it is never modified, only appended.
    assert "updated_at timestamptz" not in sql


def test_conversation_lookup_index_exists_and_nothing_speculative(sql: str) -> None:
    """The real access path — one conversation's messages in order — is indexed."""
    assert "create index messages_conversation_created_at_idx" in sql
    assert "on public.messages (conversation_id, created_at)" in sql
    assert sql.lower().count("create index") == 1


def test_rls_is_enabled(sql: str) -> None:
    """Row Level Security is turned on for the table."""
    assert "alter table public.messages enable row level security" in sql


def test_select_policy_reads_only_own_conversations_messages(sql: str) -> None:
    """SELECT requires that the caller owns the conversation the row belongs to."""
    assert 'create policy "messages_select_own"' in sql
    assert "for select" in sql
    assert "to authenticated" in sql
    assert "using (" in sql
    assert "conversations.id = messages.conversation_id" in sql
    assert "conversations.user_id = auth.uid()" in sql


def test_insert_policy_checks_author_and_conversation_ownership(sql: str) -> None:
    """INSERT carries a WITH CHECK on both the author and the target conversation."""
    assert 'create policy "messages_insert_own"' in sql
    assert "for insert" in sql
    assert "with check (" in sql
    assert "auth.uid() = user_id" in sql
    assert "conversations.user_id = auth.uid()" in sql


def test_update_and_delete_are_denied_by_default(sql: str) -> None:
    """No update and no delete policy: with RLS on, both operations are refused."""
    assert "for update" not in sql
    assert "for delete" not in sql
    assert sql.count("create policy") == 2


def test_no_broad_policy_grants_all_access(sql: str) -> None:
    """No policy opens the table beyond the caller's own conversations."""
    assert "to anon" not in sql
    assert "using (true)" not in sql
    assert "with check (true)" not in sql



def test_conversation_activity_trigger_refreshes_updated_at(sql: str) -> None:
    """A new message makes its conversation recent, in the database, for any writer."""
    assert "create or replace function public.handle_messages_conversation_activity()" in sql
    assert "after insert on public.messages" in sql
    assert "messages_refresh_conversation_activity" in sql
    assert "set updated_at = now()" in sql


def test_message_columns_are_named_once() -> None:
    """The API selects an explicit, fixed column list — no wider contract."""
    assert MESSAGE_COLUMNS == (
        "id",
        "conversation_id",
        "user_id",
        "role",
        "content",
        "created_at",
    )
    assert MESSAGE_ROLE_USER == "user"


def test_message_model_parses_a_row() -> None:
    """The domain type carries exactly the row fields with typed shapes."""
    message = Message.model_validate(
        {
            "id": "323e4567-e89b-12d3-a456-426614174000",
            "conversation_id": CONVERSATION_ID,
            "user_id": USER_ID,
            "role": "user",
            "content": "Hello",
            "created_at": "2026-10-04T12:00:00Z",
        }
    )

    assert message.role == "user"
    assert message.content == "Hello"
    assert str(message.conversation_id) == CONVERSATION_ID
    assert message.user_id == UUID(USER_ID)


def test_message_model_rejects_malformed_rows() -> None:
    """A malformed id or missing content fails validation rather than flowing on."""
    row = {
        "id": "323e4567-e89b-12d3-a456-426614174000",
        "conversation_id": CONVERSATION_ID,
        "user_id": USER_ID,
        "role": "user",
        "content": "Hello",
        "created_at": "2026-10-04T12:00:00Z",
    }

    with pytest.raises(ValidationError):
        Message.model_validate({**row, "id": "not-a-uuid"})

    without_content = dict(row)
    del without_content["content"]
    with pytest.raises(ValidationError):
        Message.model_validate(without_content)
# --- Role vocabulary (Task 8.2) ---------------------------------------------

ASSISTANT_MIGRATION = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "supabase"
    / "migrations"
    / "0004_allow_assistant_message_role.sql"
)


@pytest.fixture(scope="module")
def assistant_sql() -> str:
    """Read the role-widening migration once for the assertions below."""
    return ASSISTANT_MIGRATION.read_text(encoding="utf-8")


def test_assistant_migration_file_exists() -> None:
    """The widening is a versioned, reviewable migration, not a manual edit."""
    assert ASSISTANT_MIGRATION.is_file()


def test_assistant_is_a_valid_message_role(assistant_sql: str) -> None:
    """The check now accepts exactly `user` and `assistant`."""
    assert (
        "add constraint messages_role_user_or_assistant\n"
        "    check (role in ('user', 'assistant'))" in assistant_sql
    )


def test_the_narrower_constraint_is_replaced(assistant_sql: str) -> None:
    """The old user-only check is dropped, so the two cannot both apply."""
    assert "drop constraint if exists messages_role_user_only" in assistant_sql


def test_existing_user_messages_remain_valid(assistant_sql: str) -> None:
    """`user` is still permitted, so rows written before this migration are valid."""
    assert "'user'" in assistant_sql
    assert "role = 'user'" not in assistant_sql


@pytest.mark.parametrize("role", ["system", "tool", "function", "agent"])
def test_no_other_role_is_granted(assistant_sql: str, role: str) -> None:
    """Roles the product cannot produce stay refused."""
    assert f"'{role}'" not in assistant_sql


def test_the_widening_leaves_row_level_security_untouched(assistant_sql: str) -> None:
    """No policy, grant, or column is changed: only the role vocabulary moves.

    The messages policies are unchanged, so an assistant row is protected exactly
    as a user row is: it is readable only by the owner of its conversation.
    """
    lowered = assistant_sql.lower()
    assert "create policy" not in lowered
    assert "alter table public.messages\n    enable row level security" not in lowered
    assert "grant" not in lowered


def test_the_role_check_still_needs_a_value(assistant_sql: str) -> None:
    """The column stays `not null`; this migration widens values, not nullability."""
    # The migration touches only the constraint, so the original not-null stands.
    assert "drop not null" not in assistant_sql.lower()
