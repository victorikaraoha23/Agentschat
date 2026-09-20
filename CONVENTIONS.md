# Backend rules
1. Python 3.11. mypy --strict must pass. No bare `dict`/`list`; use dict[str, Any], list[X].
2. ruff clean. No unused code. Do not add anything the prompt did not ask for.
3. Every repository method takes workspace_id first and returns None/False for not-found.
4. Sessions: never `async with db.begin()` on a session that has already executed a statement.
   Use explicit commit()/rollback(). After a rollback, never read ORM attributes; capture primitives
   (ids, ints, strings) first. NEVER hold a DB transaction open across an LLM or network call.
5. Credits change only through src/services/credit_service.py. Every ledger write carries an
   idempotency_key.
6. Chat reserve/release contract:
   - user_message_id = uuid4(), created in 5.6
   - reserve_chat is keyed by user_message_id
   - the agent message stores meta.reply_to_user_message = <user_message_id>
   - EVERY release_chat call uses the SAME user_message_id, resolved from the agent message's
     meta — never the agent message's own id
7. Never log prompts, completions, tokens, API keys, request bodies, or PII.
8. Migrations: autogenerate, then review by hand. Every new table also gets
   `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` (Supabase exposes the public schema over PostgREST).
   Check upgrade, downgrade -1, upgrade.
9. Tests: `db` fixture (rolled back) for unit tests; `db_commit` fixture for concurrency and worker
   tests; LLM only through mock_llm; no network in tests.
10. Tests ship in the same commit as the code.

# Frontend rules
1. TypeScript strict, no `any`. tsc --noEmit, eslint, vitest must pass.
2. Server components by default. Client components only for hooks/events/state.
3. Every client-exposed env var starts with NEXT_PUBLIC_.
4. Forms: React Hook Form + Zod. All API calls go through lib/api.ts.
5. Every screen has loading, error, and empty states. Mobile responsive.
6. Streaming uses fetch + ReadableStream (EventSource cannot send Authorization headers).
7. Render markdown only via react-markdown + rehype-sanitize.
