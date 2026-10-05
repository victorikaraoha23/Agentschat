-- AgentsChat migration 0004: allow the assistant role on public.messages (Task 8.2).
--
-- Migration 0003 constrained `role` to exactly `user`, on purpose, so the schema
-- could not hold a row the application had no way to produce. Task 8.1 runs an
-- agent and returns its text but does not store it, so the only role that can
-- legitimately exist is still `user`. Task 8.2 persists the assistant reply the
-- runtime produced, and this widens the vocabulary to match.
--
-- This widens the vocabulary only. It deliberately does *not* add roles the
-- product has no way to produce: `system`, `tool`, `function`, and `agent` stay
-- refused, and a later task adds them when a real code path exists.
--
-- Ownership is unchanged. Assistant rows carry the conversation's own `user_id`,
-- so an assistant message is owned by the same authenticated user as the
-- conversation it belongs to, and the existing `messages_select_own` /
-- `messages_insert_own` policies keep protecting them: a user still reads only
-- messages in conversations they own, and still cannot insert into someone
-- else's. No policy is touched here.
--
-- The constraint is replaced rather than altered so the new name describes what
-- it now enforces. Existing rows are untouched -- `user` is still permitted, so
-- every message written before this migration remains valid and keeps its role.

alter table public.messages
    drop constraint if exists messages_role_user_only;

alter table public.messages
    add constraint messages_role_user_or_assistant
    check (role in ('user', 'assistant'));