# agents.md — AgentsChat

**Read this before every task. It is the persistent context for this codebase.**

You are the coding agent for AgentsChat. This file tells you what the product is, how the code is organized, and the rules you must follow. When something in this file conflicts with a direct user instruction, ask first. When it conflicts with another document, this file wins.

---

## 1. What AgentsChat Is

AgentsChat is a **messenger-style web app where every conversation is with an AI agent**. Users create agents, chat with one agent per conversation, and can trigger content-production jobs from chat that run a deterministic 7-stage pipeline behind the scenes and post the result back into the conversation.

**V1 user story:** A marketing person opens a chat with their "Content Writer" agent, asks for a blog post, approves a confirm card, watches 7 stages run, and receives a publication-ready article in the chat.

**Do not build in V1** (Phase 11 roadmap): group conversations, @mentions, typing indicators, reactions, read receipts, team workspaces, attachments, public API, mobile apps.

### Product decisions that are already locked

Do not re-litigate these. They are product decisions, not engineering ones.

| Decision | Value |
|---|---|
| Job cost | 17 credits base, max = est × 1.35 |
| Chat cost | 1 credit; 2 if input tokens > 8,000. Reserve 2 at send, release the difference on completion |
| Failed chat / job | Fully refunded |
| Auto-rewrite cap | 2 (counted by `auto_rewrite_count`, resets on user revision) |
| Revision charge | Standard stage 4–7 costs. Failed revision refunds only that revision |
| Trial | 14 days, 50 credits, granted via ledger |
| Concurrent jobs per workspace | 5 |
| Credits expire | No |
| BYOK calls consume credits | Yes (V1 simplification) |

---

## 2. Two-Layer Architecture

AgentsChat has **two execution paths** that share the same infrastructure. Understanding the boundary is the single most important thing in this codebase.

**Chat layer** — user↔agent messaging. Streamed token-by-token. Every message costs 1–2 credits, reserved at send and settled on completion.

**Pipeline layer** — a job is a fixed 7-stage workflow that produces a versioned deliverable. Every stage costs a fixed number of credits. Jobs are triggered either from a chat message (via a confirm card) or standalone from `/jobs/new`.

**The two layers share:**
- The LLM gateway (`src/services/llm.py`)
- The credit service (`src/services/credit_service.py`)
- The Redis streams helper
- The worker (slots pick from both queues)
- The recovery tasks

**The two layers do NOT share:**
- Session lifetimes (chat holds no session during streaming; a stage holds none during LLM calls either — see §7)
- Failure semantics (chat fails the message; a job stage fails the stage and possibly the job)
- Data models for their state (messages vs job_stages)

When you add a feature, decide which layer it belongs to first. Most confusion comes from mixing them.

---

## 3. File and Folder Layout

```
agentschat/
├── backend/
│   ├── src/
│   │   ├── main.py              # FastAPI app, lifespan, router includes
│   │   ├── config.py            # Settings (pydantic-settings), the ONLY source of env vars
│   │   ├── db.py                # Engine, SessionLocal, get_db. Import as `from src import db`
│   │   ├── api/                 # Routers (thin: validate, call service, return)
│   │   │   ├── deps.py          # get_current_user, get_ctx, require_active_subscription
│   │   │   ├── auth.py          # POST /auth/sync
│   │   │   ├── agents.py        # Agent CRUD
│   │   │   ├── conversations.py # Conversation CRUD + SSE
│   │   │   ├── messages.py      # Message send + history
│   │   │   ├── jobs.py          # Job create/read/cancel/revise, output, versions
│   │   │   ├── credits.py       # Balance, ledger, estimate
│   │   │   ├── billing.py       # Checkout, subscription info, webhook
│   │   │   └── keys.py          # BYOK endpoints
│   │   ├── models/              # SQLAlchemy ORM models, one file per table group
│   │   ├── repositories/        # Data access, workspace-scoped, no business logic
│   │   ├── services/            # Business logic. This is where most code goes.
│   │   │   ├── credit_service.py        # The only place balances change
│   │   │   ├── llm.py                   # LiteLLM gateway (call_llm, stream_llm)
│   │   │   ├── llm_json.py              # parse_json_response helper
│   │   │   ├── redis_streams.py         # publish / read / last_id
│   │   │   ├── agent_execution_service.py  # Chat streaming + settlement
│   │   │   ├── job_offer.py             # Confirm-card trigger logic
│   │   │   ├── job_messages.py          # Post completion/failure back to chat
│   │   │   ├── subscription_service.py  # Webhook event handlers
│   │   │   ├── byok_service.py          # Envelope encryption
│   │   │   ├── vault.py                 # Supabase Vault wrapper
│   │   │   └── search.py                # web_search, fetch_page, fetch_many
│   │   ├── workflows/
│   │   │   ├── types.py                 # StageContext, StageResult, StageInputError
│   │   │   ├── verification.py          # VerificationError, GATES
│   │   │   ├── executor.py              # execute_stage (3-phase), handle_failure
│   │   │   ├── failure.py               # fail_job, revert_failed_revision
│   │   │   ├── rewrite.py               # handle_claim_verify_failure
│   │   │   ├── job_recovery.py          # Stalled stage reset
│   │   │   ├── chat_recovery.py         # Stuck chat message reset
│   │   │   └── stages/                  # One handler per stage, pure functions
│   │   │       ├── brief_intake.py
│   │   │       ├── research.py
│   │   │       ├── source_verify.py
│   │   │       ├── draft.py
│   │   │       ├── claim_verify.py
│   │   │       ├── editorial_qa.py
│   │   │       └── final_output.py
│   │   ├── tasks/               # Scheduled tasks (trial expiration, webhook reprocess)
│   │   ├── utils/               # logging, telemetry, rate_limit
│   │   └── worker.py            # Slot loop, claim functions, periodic tasks
│   ├── alembic/                 # Migrations
│   ├── tests/
│   │   ├── conftest.py          # Fixtures: db, db_commit, client, mock_llm, mock_redis
│   │   ├── factories.py         # make_user, make_agent, make_job, ...
│   │   ├── concurrency.py       # run_concurrent + assertion helpers
│   │   ├── mocks/               # llm.py, fixtures.py
│   │   └── ...                  # Test files mirror src/ layout
│   └── pyproject.toml
├── frontend/
│   ├── app/
│   │   ├── (auth)/              # login, signup, forgot-password, reset-password
│   │   ├── auth/callback/       # OAuth callback route
│   │   └── (dashboard)/
│   │       ├── layout.tsx       # Two-pane shell
│   │       ├── chats/           # Chat list + [id]/ conversation view
│   │       ├── agents/          # Agent list, new, [id]
│   │       ├── jobs/            # Job list + [id] detail
│   │       ├── credits/
│   │       └── settings/        # billing, keys, integrations
│   ├── components/
│   │   ├── chat/                # ChatList, MessageBubble, Composer, Job cards
│   │   ├── agents/
│   │   ├── jobs/
│   │   └── layout/
│   ├── lib/
│   │   ├── api.ts               # apiFetch + typed helpers
│   │   ├── sse.ts               # connectSse (fetch + ReadableStream)
│   │   ├── supabase/            # client.ts, server.ts
│   │   ├── auth.ts              # signIn, signUp, syncUser
│   │   └── idempotency.ts       # newIdempotencyKey
│   ├── hooks/                   # useConversations, useMessages, useConversationStream, ...
│   └── test/msw/                # MSW server + handlers
└── CONVENTIONS.md, CLAUDE.md    # Copies of the rules in §4 and §5
```

---

## 4. Backend Rules (Non-Negotiable)

### 4.1 Types and style
- Python 3.11. `mypy --strict` must pass. No bare `dict`/`list`; use `dict[str, Any]`, `list[X]`.
- `ruff` clean. No unused imports or dead code.
- Do not add anything the task did not ask for.

### 4.2 Repository pattern
Every repository method takes `workspace_id` first. Returns `None`/`False` for not-found. Raises only for genuine errors. Repositories never call other repositories or services.

### 4.3 Session discipline — read this twice
- Never `async with db.begin()` on a session that has already executed a statement. Use explicit `await db.commit()` and `await db.rollback()`.
- **After a rollback, never read ORM attributes.** Capture ids, ints, strings before any rollback. `MissingGreenlet` in production almost always traces to this.
- **Never hold a DB transaction open across an LLM or network call.** Open the session, do the read, close it. Do the LLM call. Open a fresh session for the write.
- Import as `from src import db` and call `db.SessionLocal()` at use time. Do not `from src.db import SessionLocal` — tests retarget `src.db.SessionLocal` and your import will capture the wrong one.

### 4.4 Credits
- Balances change **only** through `src/services/credit_service.py`.
- Every ledger write carries an `idempotency_key`. The unique constraint is `(workspace_id, idempotency_key)`.
- Key conventions (documented in `credit_ledger.py`):
  - Stage charge: `consume:{stage_id}:{rewrite_cycle}`
  - Chat reservation: `chat-reserve:{user_message_id}`
  - Chat release: `chat-release:{user_message_id}`
  - Job refund: `refund:{job_id}`
  - Rewrite cycle refund: `refund:rewrite:{job_id}:{cycle}`
  - Trial grant: `grant:trial:{workspace_id}`
  - Lemon Squeezy grant: `grant:ls:{sha256_of_webhook_body}`
- Lock order: `workspace_balances` first, then `jobs`.
- `release_chat` always writes a ledger row, even at amount 0. This "seals" the key so a later recovery cannot double-release.
- **Chat reserve/release contract:** the reserve and every subsequent release are keyed by the **`user_message_id`** (the id of the *user's* message), not the agent message's own id. The agent message stores `meta.reply_to_user_message`; resolve the id from there.

### 4.5 Logging
Never log prompts, completions, tokens, API keys, request bodies, or PII. Log ids, event types, durations, and outcomes only. Use `get_logger(__name__)` from `src.utils.logging`.

### 4.6 Migrations
- `alembic revision --autogenerate`, then review the file by hand. Autogenerate misses CHECK constraints, partial unique indexes, and RLS.
- Every new table gets `op.execute("ALTER TABLE ... ENABLE ROW LEVEL SECURITY")` (Supabase exposes the public schema over PostgREST).
- Verify `upgrade head`, `downgrade -1`, `upgrade head` all succeed before committing.

### 4.7 Testing
- `db` fixture (rolled back) for unit tests.
- `db_commit` fixture for concurrency and worker tests (real commits, truncated after).
- LLM calls go through `mock_llm`. No test may hit a real network.
- Tests ship in the same commit as the code they test.

---

## 5. Frontend Rules

- TypeScript strict, no `any`. `tsc --noEmit`, `eslint`, `vitest` must pass.
- Server components by default. Use `"use client"` only when the component needs hooks, events, or browser state.
- Every client-exposed env var starts with `NEXT_PUBLIC_`.
- Forms use React Hook Form + Zod.
- All API calls go through `lib/api.ts` (`apiFetch`).
- Every screen has loading, error, and empty states. Mobile responsive.
- **Streaming uses `fetch` + `ReadableStream`, not `EventSource`.** `EventSource` cannot send `Authorization` headers.
- Markdown renders only through `react-markdown` + `rehype-sanitize`.

---

## 6. The Domain Model at a Glance

```
User ───owns── Workspace ───has── WorkspaceBalance
                    │
                    ├── Agents ──── has ──── is_pipeline_enabled
                    │
                    ├── Conversations ──── direct_agent_id ──── belongs to ─── one Agent
                    │        │
                    │        └── Messages ──── one of: user / agent / system
                    │                meta.reply_to_user_message (agent messages)
                    │
                    ├── Jobs ──── optional conversation_id, triggered_by_message_id
                    │     │       status_message_id (the chat message that shows progress)
                    │     ├── JobStages (7, sequence 1..7)
                    │     └── JobVersions (one per completed run or revision)
                    │
                    ├── CreditLedger (append-only)
                    ├── ApiKey (BYOK)
                    └── Integration (Google Docs, WordPress)
```

### Key model notes
- `messages.meta` is JSONB. Never name a column `metadata` (reserved by SQLAlchemy declarative).
- `messages.seq` is a monotonic identity column used for cursor pagination and ordering.
- There is **no `messages.job_id`** column. Jobs reference messages (`triggered_by_message_id`, `status_message_id`), never the reverse.
- `jobs.conversation_id` is nullable with `ON DELETE SET NULL`. A standalone job from `/jobs/new` has no conversation.
- `jobs.rewrite_cycles` is only a **key for consume entries**. It increments on both auto-rewrites and user revisions.
- `jobs.auto_rewrite_count` is the **auto-rewrite budget**. It increments only on auto-rewrite and resets to 0 at the start of a revision.
- `users.id` equals the Supabase `auth.users.id`. There is no default; it is supplied externally.
- `CreditLedger.amount` is signed. `type='consume'` rows are negative; `type='refund'` and `type='grant'` are positive; `type='reserve'` is negative; `type='release'` is positive. Zero-amount rows are permitted and meaningful (they seal a key).

---

## 7. Critical Patterns

### 7.1 The chat execution flow (agent message lifecycle)

```
POST /conversations/{id}/messages
  → reserve_chat (2 credits) keyed by user_message_id
  → create user message (status complete)
  → create agent message (status pending, meta.reply_to_user_message=user_id)
  → commit
  → publish message.created

Worker slot:
  → claim_agent_message: UPDATE status='streaming' WHERE id=(SELECT ... FOR UPDATE SKIP LOCKED)
  → commit (so a second worker cannot re-claim)

execute_agent_response(message_id):
  Phase A: open session, load message/conversation/agent, build history, close session
  Phase B: stream_llm with on_chunk; on_chunk buffers and flushes every ~250ms to
           set_content(partial) + publish message.updated. No DB session held during streaming.
  Phase C (success): open session, mark_complete, touch_last_message, release_chat(actual_cost),
                    commit, publish final message.updated
  Phase C (failure): mark_failed(error), release_chat(actual_cost=0), commit, publish
```

The **two-phase-with-buffered-flush** pattern is what lets 100 concurrent streams run without holding 100 database connections.

### 7.2 The pipeline execution flow (job stage lifecycle)

```
POST /jobs
  → advisory lock on workspace, count active jobs, insert job + 7 stages
  → create status message in chat (if conversation_id set), link via status_message_id
  → commit

Worker slot:
  → claim_next_stage: UPDATE status='running', attempt_count+=1
                     WHERE sequence-prev-complete AND job in (queued, running)
                     FOR UPDATE SKIP LOCKED
  → commit, start heartbeat task
  → wait_for(execute_stage(stage_id, attempt), STAGE_TIMEOUTS[name])

execute_stage (three DB phases):
  Phase A: load stage, job, ctx (outputs from upstream complete stages), preflight
           balance + budget check. Close session.
  Phase B: call the pure handler, run the gate. No session held.
  Phase C: consume_stage + fenced UPDATE ... RETURNING. If the fence returns nothing
           (attempt drift or cancelled job), rollback the charge and return.
           If last stage: create JobVersion, mark job complete, in the same transaction.
           After commit: publish progress, and post_job_completion → replaces the
           status message content with the final article.
```

**Fenced writes:** every stage status change uses `WHERE id=:id AND attempt_count=:attempt`. This is how recovery-reset stages are prevented from accepting stale results.

### 7.3 The credit reservation pattern

Chat is charged like a hotel room:

1. **At send:** `reserve_chat(2)` — a `reserve` ledger row with `amount=-2`.
2. **On completion:** `release_chat(actual_cost)` where `actual_cost` is 1 or 2 based on input tokens.
   - A `release` row with `amount = 2 - actual_cost` is written.
   - Even if `actual_cost == 2`, a `release` row with `amount=0` is written. This seals the key.
3. **On failure/timeout/recovery:** `release_chat(0)` — full refund via `amount=2`.

**Never bypass the reserve step.** A direct charge on completion would allow a burst of messages at balance 1 to all succeed.

### 7.4 Idempotency everywhere

Every state-changing endpoint accepts `Idempotency-Key`:
- `POST /conversations/{id}/messages` → unique on `(conversation_id, idempotency_key)` on messages
- `POST /jobs` → unique on `(workspace_id, idempotency_key)` on jobs
- `POST /jobs/{id}/revise` → stored in `jobs.last_revise_key`
- `POST /billing/checkout` → Lemon Squeezy handles this

Webhooks use `sha256(body)` as the `event_key` because Lemon Squeezy payloads may not carry a stable id. Unique on `(provider, event_key)`.

### 7.5 The confirm-card flow

When a user asks for content and their agent has `is_pipeline_enabled=true`:

1. The chat execution service calls `offer_job_if_applicable` before generating a reply.
2. If conditions are met, it drafts a brief (one cheap-tier call) and **mutates the pending agent message into a confirm card** — it does not create a new message.
3. The card carries `meta.type = "job_confirm"` with the draft brief and estimated credits.
4. On approve, the client `POST /jobs` with `conversation_id` and `triggered_by_message_id`.
5. On decline, the client posts a normal message with `skip_job_offer=true`.

**The mutate-in-place rule is critical.** If you create a second message instead, you leak a pending placeholder forever.

### 7.6 The job-failure / revision-recovery split

Two terminal failures with different semantics:

**First-run failure** (no `JobVersion` exists): `fail_job` marks the job failed, refunds everything consumed, and posts "Job failed" into the chat.

**Revision failure** (a `JobVersion` already exists): `fail_job` detects the version and calls `revert_failed_revision` instead. This:
- Refunds only the current cycle's stages 4–7
- Restores `job.status = 'complete'`
- Reduces `max_credits` by `REVISION_BUDGET`
- Leaves the delivered version and its chat message **byte-identical**
- Sets `meta.revision_failed` on the status message

The user must never lose an article they already paid for because a revision failed.

### 7.7 Streaming everything through Redis Streams

All real-time progress goes through `src/services/redis_streams.py`:
- Conversation stream: `conversation:{id}:events` — carries `message.created`, `message.updated`
- Job stream: `job:{id}:events` — carries `job.updated` snapshots

**Never XADD per token.** Buffer writes and publish full message payloads. On reconnect, refetch state from the DB; do not rely on event history for anything but ordering hints.

`last_id(channel)` is called **before** loading any snapshot, so a snapshot never races an event.

### 7.8 Search and fetch safety

The research stage uses `web_search` and `fetch_page`. Every fetch goes through an SSRF guard that rejects:
- Non-http(s) schemes
- Hostnames resolving to private/loopback/link-local/metadata addresses
- Every redirect target is re-checked

Never send cookies or credentials to a fetched URL.

---

## 8. The Worker

`src/worker.py` runs `worker_concurrency` (default 4) concurrent slots. Each slot:

1. Tries `claim_agent_message` first (chat is latency-sensitive).
2. Then tries `claim_next_stage` (jobs can wait a few seconds).
3. Sleeps 1–2s with jitter if nothing is available.

Slots matter because a 300-second `draft` stage must never block a chat reply. **Do not** collapse the two loops into one sequential loop.

**Periodic tasks** (60s monotonic timer, started once):
- `recover_stuck_chat_messages` — reset `streaming` messages older than 3 minutes
- `recover_stalled_stages` — reset `running` stages with stale heartbeats (> 10 minutes)
- `reprocess_stranded_webhooks` — hourly, retry unprocessed webhook events
- `expire_trials` — hourly
- Ledger reconciliation — hourly, checks `balance == sum(ledger.amount)` per workspace

**Heartbeat:** while a stage runs, a background task updates `heartbeat_at` every 30s. Recovery uses this column. Do not remove it.

**Graceful shutdown:** SIGINT/SIGTERM set a shutdown event. Slots finish their current item, then exit. In-flight stages left `running` are recovered by the next worker's periodic task.

---

## 9. The LLM Gateway

`src/services/llm.py` is the only place LiteLLM is called. Two functions:

- `call_llm(...) -> LLMResult` — non-streaming, tiered, with fallback.
- `stream_llm(..., on_chunk) -> LLMResult` — streaming; falls back only if the primary fails before the first chunk.

Both take `stage_name` and pass it through as `metadata={"stage_name": ...}` so tests and traces can dispatch.

**BYOK** is wired in via `set_key_resolver`. When a workspace key exists for the resolved provider, it is tried first. On BYOK failure the call silently falls back to the managed key and sets `used_byok=False`, plus a `byok_fallback` notice on the result.

**Cost** is computed via `litellm.completion_cost(completion_response=...)`. For streaming, `stream_options={"include_usage": True}` is passed; if usage is missing, `litellm.stream_chunk_builder` rebuilds it; if that fails, `litellm.token_counter` is used.

**Never log** the prompt, the completion, or the API key.

---

## 10. Verification Gates

Every stage's output is validated by a function in `src/workflows/verification.py`. Gates receive the output dict **and** the `StageContext` so they can compare to upstream.

If a gate raises `VerificationError`:
- For `claim_verify`: route to `handle_claim_verify_failure` (rewrite cycle)
- For any other stage: retry (up to 3 attempts), then fail

Do not add a gate that requires an LLM call. Gates are deterministic, fast, and free.

---

## 11. Testing Patterns

### Fixtures you will use
- `db` — every unit test. Rolls back.
- `db_commit` — concurrency and worker tests. Real commits; truncated after.
- `client` — httpx against the app with `db` overridden.
- `client_commit` — httpx with real sessions, for endpoint concurrency tests.
- `mock_llm` — deterministic LiteLLM. Monkeypatches `litellm.acompletion`, `litellm.completion_cost`, `litellm.token_counter`.
- `mock_redis` — flushes Redis DB 15.

### Patterns
- **Workspace isolation test:** every repository test that fetches by id must include a "foreign workspace returns None/404" case.
- **Concurrency test:** use `run_concurrent` with `db_commit`. Run 100x in a loop for anything touching credits.
- **Fenced-write test:** after a `handle_failure`, assert the stage was **not** modified if `attempt_count` drifted.
- **The stream-during-LLM test:** use `pg_stat_activity` in a slow mock handler to prove no session was held.

### What not to test
- Do not assert on exact LLM output strings.
- Do not test LiteLLM internals.
- Do not add E2E tests for edge cases — Playwright is for happy paths only.

---

## 12. Common Mistakes to Avoid

1. **Reading ORM attributes after a rollback.** Capture primitives first.
2. **Holding a session across an LLM call.** Open short sessions in each phase.
3. **Charging chat without reserving first.** Reserve at send, settle at completion.
4. **Releasing with the agent message id.** Release with the user message id.
5. **Creating a second message for job completion.** Update the status message in place.
6. **Marking a job failed when a revision fails.** Route to `revert_failed_revision`.
7. **Forgetting the fenced WHERE clause.** A stale worker will overwrite a reset stage.
8. **Using `startswith("o")` in `provider_of`.** Match against `allowed_models` and known prefixes (`o1`, `o3`).
9. **Adding a field called `metadata`.** SQLAlchemy reserves it. Use `meta`.
10. **Trying to hold `db.begin()` after a `db.get()`.** SQLAlchemy 2.0 raises. Use explicit commits.
11. **Assuming a webhook arrived before its prerequisite.** Payment events raise `DeferEvent` if `subscription_created` hasn't landed.
12. **Sending an Authorization header from `EventSource`.** It cannot. Use `fetch` + `ReadableStream`.
13. **Forgetting `NEXT_PUBLIC_` on a client env var.** It becomes `undefined` in the browser.
14. **Buffering tokens only in memory.** Flush every ~250ms so a crash leaves recoverable state.
15. **Setting `RUN_MIGRATIONS=1` on more than one Railway replica.** Migrations must run from exactly one.

---

## 13. The Standard Task Loop

For every change:

1. **Identify the layer** (chat vs pipeline vs shared).
2. **Check the rules in §4 and §5** for the language you're touching.
3. **Write or update the test first** if the contract is unclear.
4. **Run the tests locally.** `pytest` (backend) and `npm run test:ci` + `npm run typecheck` + `npm run lint` (frontend).
5. **Run `mypy --strict src`** (backend) and `tsc --noEmit` (frontend).
6. **Commit with a message that explains why**, not just what.
7. **Wait for CI green** before starting the next change.

If a test fails in a way this file or the prompt does not cover, stop and ask — do not guess at the fix.

---

## 14. Glossary

- **Agent** — user-created AI persona. Has a system prompt, model, temperature, `is_pipeline_enabled`.
- **Conversation** — a chat thread. V1 only supports `type='direct'` (one agent per conversation).
- **Message** — one chat turn. Sender is `user`, `agent`, or `system`. `meta` carries flags like `job_confirm`, `job_started`, `job_complete`, `revision_failed`.
- **Job** — one execution of the 7-stage pipeline. Has a brief, budget, and versions.
- **Stage** — one step in the pipeline. Has a sequence, an attempt count, and a heartbeat.
- **Version** — a completed deliverable. Version 1 is the initial run; versions 2+ come from revisions.
- **Reservation** — a credit hold placed at chat send. Settled at completion.
- **Rewrite cycle** — an automatic retry triggered when `claim_verify` fails. Bounded by `auto_rewrite_count`.
- **Revision** — a user-initiated re-run of stages 4–7 with feedback. Bounded by `revision_count`, not `auto_rewrite_count`.
- **BYOK** — Bring Your Own Key. A user-supplied API key for OpenAI / Anthropic / Google.
- **Gate** — a deterministic check on a stage's output.
- **Fence** — a `WHERE attempt_count=:attempt` on a write that prevents stale workers from committing.

---

*This file is the source of truth for how AgentsChat is built. When the code diverges from this file, update the file. Do not let them drift.*