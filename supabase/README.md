# Supabase project (Task 3.1+): hosted Postgres + Auth for AgentsChat.

`migrations/` holds versioned, reviewable SQL applied in filename order. Each
file must be safe to apply to a fresh project exactly once; never hand-edit a
hosted schema for anything meant to persist (root `AGENTS.md` §8).

## Applying a migration

Until a deployment task chooses tooling, apply from the Supabase Dashboard:
**SQL Editor → New query → paste the file → Run.** Verify with the checks named
in the migration's header comment.

## Migrations

| File | Purpose |
| --- | --- |
| `migrations/0001_create_profiles.sql` | `public.profiles` (id = `auth.users.id`), RLS, creation trigger |
| `migrations/0002_create_conversations.sql` | `public.conversations` (uuid id, `user_id` → `profiles.id`), RLS, owner index |
