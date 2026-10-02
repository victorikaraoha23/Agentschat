-- AgentsChat migration 0001: application-level user profiles (Task 3.3).
--
-- One `public.profiles` row per Supabase Auth user. The primary key IS the
-- Auth identity: no second user id is ever generated, so an AgentsChat user
-- cannot exist for an arbitrary UUID — the foreign key to `auth.users`
-- rejects any `id` that is not a real Auth user.
--
-- Profile creation is a database trigger on `auth.users` inserts (see below):
-- the row appears exactly when the Auth identity does, the application never
-- inserts into `profiles` directly, and `on conflict do nothing` keeps the
-- trigger idempotent so a retried insert cannot create duplicates.
--
-- RLS is enabled and fail-closed: no `update`/`delete` policy exists at all
-- (the initial model has no user-editable fields, so no update permission is
-- granted), and the single `select` policy only matches the caller's own row
-- (`auth.uid() = id`).

create table public.profiles (
  -- Supabase Auth user id. Same type as `auth.users.id` (uuid) so the
  -- reference is exact; `primary key` additionally gives uniqueness.
  id uuid primary key references auth.users (id) on delete cascade,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.profiles is
  'Application-level user record, one per Supabase Auth user (Task 3.3).';
comment on column public.profiles.id is
  'Supabase Auth user id (auth.users.id); never a separately generated identity.';

alter table public.profiles enable row level security;

-- Authenticated callers can read exactly their own profile row.
create policy "profiles_select_own"
  on public.profiles
  for select
  to authenticated
  using (auth.uid() = id);

-- Keep `updated_at` honest even though nothing writes it yet; a later task
-- that adds user-editable fields will revisit this trigger alongside its
-- update policy.
create or replace function public.handle_profiles_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger profiles_set_updated_at
  before update on public.profiles
  for each row
  execute function public.handle_profiles_updated_at();

-- Create the profile exactly when the Auth identity appears. `security
-- definer` runs the function with the rights to insert into `profiles`
-- (ordinary callers have no insert grant at all); `set search_path = public`
-- pins name resolution so the trigger cannot be redirected. `on conflict do
-- nothing` makes redelivery idempotent; the update policy deliberately stays
-- absent, so nothing about this row can be changed through the API.
create or replace function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id) values (new.id)
  on conflict (id) do nothing;
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row
  execute function public.handle_new_auth_user();
