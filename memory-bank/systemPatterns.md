# System Patterns

Architectural decisions and recurring patterns. Section references (`§n`) point into `Agents.md`,
which is authoritative.

## 1. Two-layer architecture — the single most important thing

Two execution paths share infrastructure and must never be confused.

| | Chat layer | Pipeline layer |
|---|---|---|
| Purpose | user ↔ agent messaging | produce a versioned deliverable |
| Unit of work | one message | one job (7 stages) → one version |
| Timing | streamed token-by-token | fixed stages, minutes each |
| Cost model | 1–2 credits, reserved then settled | fixed credits per stage |
| Failure semantics | fail the message | fail the stage, possibly the job |
| State | `messages` | `job_stages`, `job_versions` |

**Shared:** LLM gateway (`src/services/llm.py`), credit service
(`src/services/credit_service.py`), the Redis streams helper, the worker, and the recovery tasks.

**Not shared:** session lifetimes, failure semantics, state models.

Decide which layer a feature belongs to **before** writing code. Most confusion in this codebase
comes from mixing the two.

## 2. Chat execution flow — agent message lifecycle (§7.1)

```
POST /conversations/{id}/messages
  → reserve_chat(2), keyed by user_message_id
  → create user message (status complete)
  → create agent message (status pending, meta.reply_to_user_message = user_id)
  → commit, publish message.created

Worker slot:
  → claim_agent_message: UPDATE status='streaming'
        WHERE id=(SELECT ... FOR UPDATE SKIP LOCKED)
  → commit                      # so a second worker cannot re-claim

execute_agent_response(message_id):
  Phase A  open session, load message/conversation/agent, build history, close session
  Phase B  stream_llm with on_chunk → buffer and flush ~every 250 ms via set_content(partial)
           + publish message.updated. NO DB session is held while streaming.
  Phase C  success: mark_complete, touch_last_message, release_chat(actual_cost), commit, publish
           failure: mark_failed(error), release_chat(0), commit, publish
```

The **two-phase-with-buffered-flush** pattern is what lets ~100 concurrent streams run without
holding 100 database connections.

## 3. Pipeline execution flow — job stage lifecycle (§7.2)

```
POST /jobs
  → advisory lock on workspace, count active jobs, insert job + 7 stages
  → create status message in chat (if conversation_id), link via status_message_id
  → commit

Worker slot:
  → claim_next_stage: UPDATE status='running', attempt_count += 1
        WHERE previous-sequence-complete AND job in ('queued','running')
        FOR UPDATE SKIP LOCKED
  → commit, start heartbeat task
  → wait_for(execute_stage(stage_id, attempt), STAGE_TIMEOUTS[name])

execute_stage — three DB phases:
  Phase A  load stage, job, ctx (outputs of upstream complete stages), preflight balance + budget.
           Close session.
  Phase B  call the pure handler and run the gate. No session held.
  Phase C  consume_stage + fenced UPDATE ... RETURNING.
           If the fence returns nothing (attempt drift or a cancelled job): roll back the charge
           and return. If this is the last stage: create the JobVersion and mark the job complete
           in the same transaction. After commit: publish progress, then post_job_completion,
           which replaces the status message content with the final article.
```

**Fenced writes.** Every stage status change is written as
`WHERE id=:id AND attempt_count=:attempt`. This is what stops a recovery-reset stage from accepting
a stale worker's result. Never drop the fence.

## 4. Credit reservation pattern — chat is charged like a hotel room (§7.3)

1. **At send:** `reserve_chat(2)` writes a `reserve` ledger row with `amount=-2`.
2. **On completion:** `release_chat(actual_cost)`, where `actual_cost` is 1 or 2 depending on input
   tokens. A `release` row with `amount = 2 - actual_cost` is written — **even when that amount is
   0**, which seals the idempotency key so a later recovery cannot double-release.
3. **On failure / timeout / recovery:** `release_chat(0)` — a full refund.

Never bypass the reserve step. Charging directly on completion would let a burst of messages at
balance 1 all succeed.

### The reserve/release key contract (the #1 source of production bugs)

- `reserve_chat` is keyed by the **`user_message_id`** — the `uuid4` created before the messages.
- The agent message stores `meta.reply_to_user_message = <user_message_id>`.
- **Every** `release_chat` call resolves that same `user_message_id` from the agent message's meta —
  never the agent message's own id.

### Ledger key conventions

| Purpose | Key |
|---|---|
| Stage charge | `consume:{stage_id}:{rewrite_cycle}` |
| Chat reservation | `chat-reserve:{user_message_id}` |
| Chat release | `chat-release:{user_message_id}` |
| Job refund | `refund:{job_id}` |
| Rewrite-cycle refund | `refund:rewrite:{job_id}:{cycle}` |
| Trial grant | `grant:trial:{workspace_id}` |
| Lemon Squeezy grant | `grant:ls:{sha256_of_webhook_body}` |

`CreditLedger.amount` is signed: `consume` and `reserve` are negative; `release`, `refund`, and
`grant` are positive. Zero-amount rows are permitted and meaningful. Lock order when both are
needed: `workspace_balances` first, then `jobs`.

## 5. Idempotency everywhere (§7.4)

| Endpoint | Key / uniqueness |
|---|---|
| `POST /conversations/{id}/messages` | unique `(conversation_id, idempotency_key)` on messages |
| `POST /jobs` | unique `(workspace_id, idempotency_key)` on jobs |
| `POST /jobs/{id}/revise` | `jobs.last_revise_key` |
| `POST /billing/checkout` | Lemon Squeezy handles it |
| Webhooks | `sha256(body)` as `event_key`, unique `(provider, event_key)` |

Every ledger write carries an `idempotency_key`, unique on `(workspace_id, idempotency_key)`.

## 6. The confirm-card flow (§7.5)

When a user asks for content and their agent has `is_pipeline_enabled=true`:

1. The chat execution service calls `offer_job_if_applicable` **before** generating a reply.
2. If the conditions are met it drafts a brief (one cheap-tier call) and **mutates the pending agent
   message into a confirm card** — it does not create a new message.
3. The card carries `meta.type = "job_confirm"` with the draft brief and the estimated credits.
4. Approve → the client `POST /jobs` with `conversation_id` and `triggered_by_message_id`.
5. Decline → the client posts a normal message with `skip_job_offer=true`.

**Mutate in place.** Creating a second message leaks a pending placeholder forever.

## 7. The job-failure / revision-recovery split (§7.6)

Two terminal failures with different semantics:

**First-run failure** — no `JobVersion` exists. `fail_job` marks the job failed, refunds everything
consumed, and posts "Job failed" into the chat.

**Revision failure** — a `JobVersion` already exists. `fail_job` detects the version and calls
`revert_failed_revision` instead, which:

- refunds only the current cycle's stages 4–7
- restores `job.status = 'complete'`
- reduces `max_credits` by `REVISION_BUDGET`
- leaves the delivered version and its chat message **byte-identical**
- sets `meta.revision_failed` on the status message

The user must never lose an article they already paid for because a revision failed.

## 8. Rewrite cycles vs revisions — two separate counters

Easy to conflate, never interchangeable:

| | Auto-rewrite | User revision |
|---|---|---|
| Trigger | the `claim_verify` gate fails | the user asks for changes |
| Counter | `jobs.auto_rewrite_count` | `jobs.revision_count` |
| Cap | 2 | bounded by `revision_count` |
| Reset | resets to 0 at the start of a revision | — |
| Stages re-run | from the failing point | 4–7 |

`jobs.rewrite_cycles` is *only* a key for `consume` entries — it increments on **both** auto-rewrites
and user revisions. Do not use it as a budget.

## 9. Real-time via Redis Streams (§7.7)

| Stream | Carries |
|---|---|
| `conversation:{id}:events` | `message.created`, `message.updated` |
| `job:{id}:events` | `job.updated` snapshots |

- Never `XADD` per token. Buffer writes and publish full message payloads.
- On reconnect, refetch state from the DB; use events only as ordering hints.
- Call `last_id(channel)` **before** loading any snapshot, so a snapshot never races an event.

## 10. Verification gates (§10)

Every stage's output is validated by a function in `src/workflows/verification.py`. Gates receive the
output dict **and** the `StageContext`, so they can compare against upstream results.

- `claim_verify` gate failure → `handle_claim_verify_failure` (auto-rewrite cycle)
- Any other gate failure → retry (up to 3 attempts), then fail the stage

Gates must be **deterministic, fast, and free** — never add a gate that requires an LLM call.

## 11. The LLM gateway (§9)

`src/services/llm.py` is the only place LiteLLM is called. Two functions:

- `call_llm(...) -> LLMResult` — non-streaming, tiered, with fallback
- `stream_llm(..., on_chunk) -> LLMResult` — streaming; falls back only if the primary fails before
  the first chunk

Both take `stage_name` and pass it through as `metadata={"stage_name": ...}` so tests and traces can
dispatch on it.

**BYOK** is wired in through `set_key_resolver`. When a workspace key exists for the resolved provider
it is tried first. On BYOK failure the call silently falls back to the managed key, sets
`used_byok=False`, and attaches a `byok_fallback` notice to the result.

**Cost** comes from `litellm.completion_cost(completion_response=...)`. For streaming,
`stream_options={"include_usage": True}` is passed; if usage is missing,
`litellm.stream_chunk_builder` rebuilds it; if that fails, `litellm.token_counter` is used.

**Never log** the prompt, the completion, or the API key.

## 12. The worker model (§8)

`src/worker.py` runs `worker_concurrency` (default 4) independent slots. Each slot:

1. tries `claim_agent_message` first — chat is latency-sensitive
2. then tries `claim_next_stage` — jobs can wait a few seconds
3. sleeps 1–2 s with jitter when nothing is available

Slots exist so a 300-second `draft` stage cannot block a chat reply. **Do not** collapse the two loops
into one sequential loop.

Periodic tasks (60 s monotonic timer, started once):

| Task | Cadence / threshold |
|---|---|
| `recover_stuck_chat_messages` | `streaming` messages older than 3 minutes |
| `recover_stalled_stages` | `running` stages with stale heartbeats (> 10 minutes) |
| `reprocess_stranded_webhooks` | hourly |
| `expire_trials` | hourly |
| Ledger reconciliation | hourly — asserts `balance == sum(ledger.amount)` per workspace |

**Heartbeat:** while a stage runs, a background task updates `heartbeat_at` every 30 s. Recovery reads
that column — do not remove it.

**Graceful shutdown:** SIGINT/SIGTERM set a shutdown event; slots finish the current item, then exit.
In-flight stages left `running` are recovered by the next worker's periodic task.

## 13. Layering, ownership, and logging rules

- **Routers are thin:** validate → call a service → return.
- **Repositories:** `workspace_id` first, return `None`/`False` for not-found, raise only for genuine
  errors, never call other repositories or services, no business logic.
- **Balances change only** through `src/services/credit_service.py`.
- **LiteLLM is called only** from `src/services/llm.py`.
- **Sessions:** never `async with db.begin()` on a session that has already executed a statement — use
  explicit `commit()`/`rollback()`. After a rollback, never read ORM attributes; capture primitives
  (ids, ints, strings) first. Never hold a transaction open across an LLM or network call. Import
  `from src import db` and call `db.SessionLocal()` at use time — tests retarget `src.db.SessionLocal`,
  so `from src.db import SessionLocal` captures the wrong one.
- **Logging:** never log prompts, completions, tokens, API keys, request bodies, or PII. Log ids,
  event types, durations, and outcomes with `get_logger(__name__)` from `src.utils.logging`.

## 14. Domain model at a glance (§6)

```
User ──owns── Workspace ──has── WorkspaceBalance
                 │
                 ├── Agents ────────── is_pipeline_enabled
                 ├── Conversations ─── direct_agent_id ──→ exactly one Agent
                 │       └── Messages ── user / agent / system
                 │             meta.reply_to_user_message (agent messages)
                 ├── Jobs ── optional conversation_id, triggered_by_message_id,
                 │            status_message_id
                 │       ├── JobStages   (7, sequence 1..7)
                 │       └── JobVersions (one per completed run or revision)
                 ├── CreditLedger (append-only)
                 ├── ApiKey (BYOK)
                 └── Integration (Google Docs, WordPress)
```

Model gotchas:

- `messages.meta` is JSONB. Never name a column `metadata` — SQLAlchemy declarative reserves it.
- `messages.seq` is a monotonic identity column used for cursor pagination and ordering.
- There is **no `messages.job_id`**. Jobs reference messages, never the reverse.
- `jobs.conversation_id` is nullable with `ON DELETE SET NULL` — a standalone job has none.
- `users.id` equals the Supabase `auth.users.id`; there is no default, it is supplied externally.

## 15. The mistakes that keep happening (§12)

Check new code against this list before committing.

1. Reading ORM attributes after a rollback — capture primitives first.
2. Holding a session across an LLM call — open short sessions per phase.
3. Charging chat without reserving first.
4. Releasing credits with the *agent* message id instead of the user message id.
5. Creating a second message for job completion instead of updating the status message in place.
6. Marking a job failed when a *revision* fails — route to `revert_failed_revision`.
7. Forgetting the fenced `WHERE attempt_count=:attempt` clause.
8. Using `startswith("o")` in `provider_of` — match `allowed_models` and known prefixes (`o1`, `o3`).
9. Adding a field named `metadata`.
10. Trying `db.begin()` after a `db.get()` — SQLAlchemy 2.0 raises; use explicit commits.
11. Assuming a webhook arrived before its prerequisite — payment events raise `DeferEvent` until
    `subscription_created` lands.
12. Sending an `Authorization` header from `EventSource` — it cannot; use fetch + ReadableStream.
13. Forgetting `NEXT_PUBLIC_` on a client env var.
14. Buffering streamed tokens only in memory — flush every ~250 ms.
15. Setting `RUN_MIGRATIONS=1` on more than one Railway replica.
