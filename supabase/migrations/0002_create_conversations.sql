-- AgentsChat migration 0002: conversations owned by one authenticated user (Task 5.1).
--
-- One `public.conversations` row belongs to exactly one AgentsChat user:
-- `user_id` references `public.profiles (id)` — not `auth.users` directly —
-- so the existing identity chain is explicit (`auth.users -> profiles ->
-- conversations`) and a conversation can never name an arbitrary UUID: the
-- foreign key rejects any `user_id` without a profile row, and a profile row
-- can only exist for a real Auth user (migration 0001).
--
-- `title` is nullable with no default: the initial model stores no title until
-- a later task sets one (no AI-generated titles yet). `created_at` and
-- `updated_at` are database-managed via `now()` defaults plus the same
-- before-update trigger pattern as migration 0001.
--
-- RLS is enabled and fail-closed: four policies, each scoped to the caller's
-- own rows (`auth.uid() = user_id`). In particular the `insert` policy carries
-- a `with check` on `user_id`, so a client-supplied `user_id` naming another
-- user is rejected by the database — ownership always comes from the
-- authenticated identity, never from request data.

create table public.conversations (
  -- Database-generated UUID primary key; the application never assigns ids.
  id uuid primary key default gen_random_uuid(),
  -- Owner: must name an existing profile row (hence, transitively, a real
  -- Auth user). `not null` forbids ownerless rows; `on delete cascade` removes
  -- a user's conversations when their profile goes.
  user_id uuid not null references public.profiles (id) on delete cascade,
  -- Nullable until a later task assigns titles; no default is invented here.
  title text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.conversations is
  'One authenticated user''s conversations (Task 5.1); ownership via user_id -> profiles.id.';
comment on column public.conversations.user_id is
  'Owner profile id (public.profiles.id); never a separately generated identity.';

-- The real query pattern is "this user's conversations", so index the owner.
-- Named explicitly; no speculative indexes beyond this one.
create index conversations_user_id_idx on public.conversations (user_id);

alter table public.conversations enable row level security;

-- Authenticated callers can read exactly their own conversations.
create policy "conversations_select_own"
  on public.conversations
  for select
  to authenticated
  using (auth.uid() = user_id);

-- Authenticated callers can create rows only for themselves: the `with check`
-- rejects any `user_id` that is not the caller's own identity.
create policy "conversations_insert_own"
  on public.conversations
  for insert
  to authenticated
  with check (auth.uid() = user_id);

-- Authenticated callers can update only their own conversations, and cannot
-- move a row to another owner: both the existing row and the proposed new row
-- must satisfy the ownership check.
create policy "conversations_update_own"
  on public.conversations
  for update
  to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Authenticated callers can delete only their own conversations.
create policy "conversations_delete_own"
  on public.conversations
  for delete
  to authenticated
  using (auth.uid() = user_id);

-- Keep `updated_at` honest on every modification, mirroring the profiles
-- trigger from migration 0001 (a dedicated function keeps each migration
-- self-contained and independently reviewable).
create or replace function public.handle_conversations_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger conversations_set_updated_at
  before update on public.conversations
  for each row
  execute function public.handle_conversations_updated_at();
