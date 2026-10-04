-- AgentsChat migration 0003: messages inside a conversation (Task 6.2).
--
-- One `public.messages` row is one message in one conversation:
--
--   auth.users -> profiles -> conversations -> messages
--
-- `conversation_id` references `public.conversations (id)` and `user_id`
-- references `public.profiles (id)`, so a message can never name a conversation
-- that does not exist and can never be ownerless: the foreign keys reject an
-- orphan message and reject a `user_id` with no profile row. `on delete cascade`
-- removes a conversation's messages when the conversation is deleted, and a
-- user's messages when their profile goes.
--
-- `role` is constrained to `user` for now. Only the user side of a
-- conversation exists in this task; a later agent task widens this check
-- deliberately, in a migration, rather than the column accepting any string
-- from the start. The application states the role explicitly, so there is no
-- default that could quietly guess it.
--
-- `content` is plain text. It is stored and rendered as text, never as markup,
-- and the check constraint refuses an empty or whitespace-only message at the
-- database as well. The maximum length is a product rule enforced by the API
-- (`MAX_MESSAGE_CONTENT_LENGTH`), exactly as the conversation title limit is;
-- the database owns the "not blank" guarantee rather than a second, drifting
-- copy of the number.
--
-- RLS is enabled and fail-closed. Read and insert are the only two operations
-- this task supports, so only two policies exist: SELECT and INSERT each
-- require the caller to own the *conversation* the message belongs to, which is
-- what keeps a message inside its conversation's ownership boundary. There is
-- deliberately **no update and no delete policy**: with RLS enabled and no
-- policy, those operations are denied, so a message cannot be edited or removed
-- by anyone until a task that owns that behavior writes the policy.
--
-- The `insert` policy's `with check` covers both halves — the caller must be the
-- author *and* the owner of the target conversation — so a client that names
-- another user's `user_id`, or another user's `conversation_id`, is rejected by
-- the database. Ownership always comes from the authenticated identity, never
-- from request data.

create table public.messages (
  -- Database-generated UUID primary key; the application never assigns ids.
  id uuid primary key default gen_random_uuid(),
  -- The conversation this message belongs to. No orphans: the foreign key
  -- rejects a `conversation_id` with no conversation row.
  conversation_id uuid not null references public.conversations (id) on delete cascade,
  -- Author: the same identity chain as a conversation owner, so the column can
  -- never name an arbitrary UUID.
  user_id uuid not null references public.profiles (id) on delete cascade,
  -- `user` is the only role this task supports; the constraint is widened by a
  -- later migration when assistant messages exist.
  role text not null,
  content text not null,
  created_at timestamptz not null default now(),
  constraint messages_role_user_only check (role = 'user'),
  constraint messages_content_not_blank check (char_length(btrim(content)) > 0)
);

comment on table public.messages is
  'Messages a user sent in one of their own conversations (Task 6.2).';
comment on column public.messages.user_id is
  'Author profile id (public.profiles.id); always the authenticated caller.';
comment on column public.messages.content is
  'Plain text as typed. Never markup, never rendered as HTML.';

-- The real query pattern — and the one the next task needs — is "this
-- conversation's messages in chronological order", so the composite index
-- matches that exact access path. Named explicitly; no speculative indexes.
create index messages_conversation_created_at_idx
  on public.messages (conversation_id, created_at);

alter table public.messages enable row level security;

-- Authenticated callers read the messages of the conversations they own.
create policy "messages_select_own"
  on public.messages
  for select
  to authenticated
  using (
    exists (
      select 1
      from public.conversations
      where conversations.id = messages.conversation_id
        and conversations.user_id = auth.uid()
    )
  );

-- Authenticated callers insert only as themselves, and only into a conversation
-- they own: both halves are checked by the database on the proposed row.
create policy "messages_insert_own"
  on public.messages
  for insert
  to authenticated
  with check (
    auth.uid() = user_id
    and exists (
      select 1
      from public.conversations
      where conversations.id = messages.conversation_id
        and conversations.user_id = auth.uid()
    )
  );

-- New activity in a conversation must show up as recent activity on the
-- conversation itself, so a conversation list ordered by `updated_at` stays
-- truthful. Doing it in a trigger keeps that true for every writer — the API
-- today, and any future message path — without a worker and without the
-- application writing timestamps. The parent row's own before-update trigger
-- (migration 0002) keeps its assignment consistent with the rest of the schema.
create or replace function public.handle_messages_conversation_activity()
returns trigger
language plpgsql
as $$
begin
  update public.conversations
     set updated_at = now()
   where id = new.conversation_id;
  return null;
end;
$$;

create trigger messages_refresh_conversation_activity
  after insert on public.messages
  for each row
  execute function public.handle_messages_conversation_activity();
