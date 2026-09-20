# Project Brief — AgentsChat

> This file summarizes `Agents.md` (repo root), which remains the source of truth. If the two
> disagree, `Agents.md` wins — then fix this file.

## One-liner

AgentsChat is a **messenger-style web app where every conversation is with an AI agent**: users
create agents, chat one agent per conversation, and can trigger content-production jobs that run a
deterministic 7-stage pipeline and post the finished deliverable back into the conversation.

## V1 user story

A marketing person opens a chat with their "Content Writer" agent, asks for a blog post, approves a
confirm card, watches 7 stages run, and receives a publication-ready article in the chat.

## In scope (V1)

- Agents: user-created personas with a system prompt, model, temperature, `is_pipeline_enabled`
- Conversations: `type='direct'` only — one agent per conversation
- Streamed chat replies, priced per message
- The 7-stage pipeline, triggered from chat (confirm card) or standalone from `/jobs/new`
- Versioned deliverables and user-initiated revisions
- Credits, append-only ledger, 14-day trial, Lemon Squeezy billing, BYOK keys
- Web search + page fetch, used by the research stage

## Out of scope (Phase 11 roadmap)

Group conversations, @mentions, typing indicators, reactions, read receipts, team workspaces,
attachments, public API, mobile apps.

## Locked product decisions — do not re-litigate

| Decision | Value |
|---|---|
| Job cost | 17 credits base, max = est × 1.35 |
| Chat cost | 1 credit; 2 if input tokens > 8,000. Reserve 2 at send, release the difference on completion |
| Failed chat / job | Fully refunded |
| Auto-rewrite cap | 2 (counted by `auto_rewrite_count`, resets on user revision) |
| Revision charge | Standard stage 4–7 costs. A failed revision refunds only that revision |
| Trial | 14 days, 50 credits, granted via the ledger |
| Concurrent jobs per workspace | 5 |
| Credits expire | No |
| BYOK calls consume credits | Yes (V1 simplification) |

## The 7 stages, in order

1. `brief_intake`
2. `research`
3. `source_verify`
4. `draft`
5. `claim_verify` — the only stage whose gate failure routes into an auto-rewrite cycle
6. `editorial_qa`
7. `final_output`

## Success looks like

The V1 user story completing end to end: brief → confirm card → 7 stages → a publication-ready
article in the chat, with every credit accounted for in the ledger and no delivered work lost when
a later revision fails.
