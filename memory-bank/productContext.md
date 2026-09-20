# Product Context

## The problem

Producing a publication-ready article is not one prompt. It is research, source verification,
drafting, fact-checking, editorial QA, and output formatting. A single chat turn cannot do that
reliably, and a chat UI cannot show progress through work that takes minutes.

Two concrete failures AgentsChat exists to fix:

1. **Unreliable single-shot output.** One prompt produces confident prose and invented sources.
   AgentsChat forces the work through a fixed, gated stage sequence instead.
2. **Invisible long-running work.** A five-minute job looks like a hang in a normal chat. AgentsChat
   streams stage-by-stage progress back into the conversation so the user watches the work happen.

## How it should feel

- Like a **messenger**, not a dashboard or a wizard. Chat is the primary surface; agents, jobs,
  credits, and settings exist to support it.
- The user never has to think about stages. They approve a confirm card and watch.
- Work already paid for is never lost — a failed revision leaves the delivered version byte-identical.
- Every reply and every job has a visible, understandable cost.

## Users

Primary: **marketing and content people** who need publication-ready artifacts and are willing to
approve a plan before the machine runs. They are not prompt engineers.

## Surfaces (V1)

| Surface | Purpose |
|---|---|
| `frontend/app/(auth)/` | login, signup, forgot-password, reset-password |
| `frontend/app/auth/callback/` | OAuth callback route |
| `frontend/app/(dashboard)/chats/` | conversation list + conversation view (chat, confirm cards, job progress) |
| `frontend/app/(dashboard)/agents/` | create / edit / list agent personas |
| `frontend/app/(dashboard)/jobs/` | standalone job creation + job detail with versions |
| `frontend/app/(dashboard)/credits/` | balance and ledger |
| `frontend/app/(dashboard)/settings/` | billing, BYOK keys, integrations |

`frontend/app/(dashboard)/layout.tsx` is the two-pane shell that wraps all of the above.

## The two moments that define the product

1. **The confirm card.** Asking for content does not silently start a 17-credit job. The agent drafts
   a brief (one cheap-tier call) and asks. Approval is a deliberate, priced action.
2. **The completion message.** The deliverable reaches the user by updating the job's status message
   in place — the chat *is* the delivery surface, so no second message is ever created for it.

Both are failure-prone if implemented naively (a leaked pending placeholder; a lost article on
revision failure), which is why `Agents.md` §7.5 and §7.6 treat them as critical patterns.

## Non-goals for V1

No group chat, no social features, no public API, no mobile app. See `projectbrief.md`.
