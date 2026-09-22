# AgentsChat — AGENTS.md

**This file is the engineering constitution for AgentsChat.** It is the standing instruction set for AI
coding agents (and human engineers) working in this repository. Where it says **must**, **never**, or
**do not**, treat it as a hard rule, not a style preference. Every task is expected to be reviewable
against this document.

## Scope and Precedence

- This file governs **AgentsChat application code**: the Next.js web app, the FastAPI API, Supabase
  schema/migrations/policies, AgentsChat execution workers, and AgentsChat tests, config, and docs.
- **Hermes runtime source already exists in this checkout** (`agent/`, `gateway/`, `hermes_cli/`,
  `tools/`, `plugins/`, `skills/`, `cron/`, `ui-tui/`, `tui_gateway/`, `acp_adapter/`, `apps/`, `web/`,
  `evals/`, `tests/`, ...). Those areas have their own `AGENTS.md` files. Read the area guide before
  editing there — see **Appendix A**.
- **`web/` in this checkout is Hermes's dashboard SPA. It is not the AgentsChat web application.**
- The AgentsChat application code **does not exist yet**. Tasks create it incrementally. Do not create
  scaffolds, folders, services, tables, or dependencies that the current task does not require.
- Precedence: for Hermes internals, the Hermes area guide wins. For AgentsChat code, this file wins. If a
  task instruction conflicts with this file, stop and surface the conflict instead of guessing.

---

## 1. Project Mission

**What AgentsChat is.** AgentsChat is a fully hosted, beginner-friendly AI-agent workspace. Users talk to
AI agents through a simple chat-based interface while the underlying system handles agent execution,
tools, files, memory, and — eventually — multi-agent workflows.

**The problem it solves.** Getting real work out of capable AI agents normally requires assembling a
runtime, model providers, tool configuration, sandboxing, credentials, and hosting. AgentsChat removes
that burden: a user signs in, describes what they need in plain language, and the hosted system does the
work and returns the result.

**AgentsChat vs Hermes.**

| | AgentsChat (product layer) | Hermes (agent runtime layer) |
|---|---|---|
| Responsibility | accounts, workspaces, chat UX, agent configuration surfaces, product data & ownership, authorization, usage limits, orchestration of product operations | agent execution loop, runtime tool behavior, agent-level runtime capabilities |
| Visible to users | yes — this *is* the product | no — it is an implementation dependency |
| Location | AgentsChat application code (created by its own tasks) | the Hermes source already in this checkout |

These responsibilities **must remain clearly separated** (§2, §3, §11).

**Long-term product direction.** AgentsChat is intended to become serious production software, not a
prototype. That means durable records of what happened, honest execution status, human review and control
over consequential actions, and multi-agent workflows added only when the product genuinely requires
them. Shortcuts taken now are conveniences to be revisited deliberately — never assumed to be
production-acceptable by default.

**Complexity hidden from users.** Ordinary users must never need to understand providers, models, tool
permissions, sandboxes, workers, retries, queues, or failure taxonomies. Complexity is hidden by good
product design and simple surfaces — **not** by concealing failure. Progress and errors must stay honest:
hide the machinery, never the truth about the state of the user's work.

## 2. Architecture Principles — Separation of Concerns

Approved high-level direction: **Next.js → FastAPI → Supabase**, with **Hermes** as the agent runtime
executing in a **separate execution environment/workers**. Responsibilities are exclusive:

### Next.js — web application / frontend
Owns: UI, presentation, client interaction, frontend state, frontend routing.
- Talks to the FastAPI API only. Does not call Hermes, model providers, or the database directly, and does
  not use privileged service-role credentials.
- Must not own application/business rules (ownership, entitlements, quota, run-state transitions).

### FastAPI — backend / API
Owns: API endpoints, application and business logic, validation, authorization decisions, and the
orchestration of application operations (starting runs, persisting results, enforcing limits).
- Owns the AgentsChat side of the Hermes contract.
- Must not reimplement agent runtime behavior that belongs to Hermes.

### Supabase — authentication infrastructure and persistent application data
Owns: authentication/identity infrastructure, persistent application data, and storage where appropriate.
- Enforces ownership invariants through schema constraints and Row Level Security.
- Is not a hiding place for business logic that should be testable and reviewable in the API.

### Hermes — agent runtime
Owns: agent execution, agent runtime behavior, and the runtime tool capabilities that belong to Hermes.
- Runs in its own execution environment/workers, out of the API request path.

### Non-duplication rule
**AgentsChat must not unnecessarily duplicate Hermes functionality.** Do not rebuild the agent loop, tool
calling, model/provider routing, sandboxed execution, agent memory, or agent-level retry logic in the API
or the UI. Just as importantly, do not push AgentsChat product concerns (accounts, tenancy, billing,
entitlements, workspace policy, product authorization) down into Hermes. If a requirement appears to
demand either kind of duplication, stop and raise it as a design question.

## 3. Dependency Direction

Allowed direction (arrow = "may depend on"):

```
Next.js UI  →  FastAPI API  →  AgentsChat services  →  data access  →  Supabase
FastAPI services  →  Hermes adapter  →  Hermes runtime (separate process/environment)
```

Rules:

1. **The frontend communicates with the backend only through defined API boundaries.** No database
   clients, no service-role keys, no Hermes or MCP endpoints, and no provider SDKs in the browser.
2. **Application business logic must not be scattered through UI components.** Components render and
   format; they do not own rules such as ownership checks, quotas, or run-state transitions.
3. **Hermes-specific implementation details must remain behind an explicit adapter/interface.** The rest
   of AgentsChat depends on the AgentsChat/Hermes contract rather than directly on Hermes internals: no
   Hermes imports, Hermes config keys, or Hermes internal types outside that boundary.
4. **Depend on the contract, not the internals.** The adapter exposes typed, AgentsChat-shaped
   operations. Do not reach into Hermes private helpers, internal file formats, or undocumented behavior.
5. **Database access must not be scattered.** Persistence goes through an explicit data-access layer with
   typed functions — not ad-hoc queries inside route handlers, workers, or components.
6. **No dependency cycles.** If two modules need each other, extract the shared piece into a lower layer.

An import that violates this section is a defect even when the code appears to work.

## 4. Simplicity Rule

> **Use the simplest architecture that correctly satisfies the current requirement.**

Do not introduce infrastructure because it might be useful someday. **Future scalability alone is not
sufficient justification.** Unless a concrete, current product or production requirement has been
established and documented, do **not** introduce any of:

- Redis or Upstash
- Kafka or RabbitMQ
- Kubernetes
- microservices (splitting the product into separately deployed services)
- vector databases or embedding stores
- event buses / event sourcing
- additional databases
- additional cloud services
- complex job queues

**Reconciliation with the approved architecture:** the separate Hermes execution
environment/workers exist for **agent execution isolation** — that is the approved, justified
requirement. They are not a general-purpose queueing or eventing platform, and the existence of that
environment does not justify the items above.

If complexity genuinely becomes necessary, it must be introduced deliberately:

1. state the concrete requirement and the evidence for it;
2. describe the simpler alternatives considered and why each fails;
3. record the decision where the change is reviewed (task/PR description) and update this file if the
   decision changes the standing rules;
4. then implement it as one focused, documented change.

## 5. Atomic Development Rule

Every implementation task must remain atomic. Agents must:

- **implement only the requested task**;
- **avoid unrelated refactoring**, renaming, reformatting, or dependency upgrades;
- **avoid speculative features** ("we will almost certainly need this later");
- **avoid premature abstractions** (base classes, plugin systems, generic frameworks for one caller);
- **avoid silently expanding scope** (no bonus endpoints, no extra tables/columns, no extra screens,
  no "while I was here" cleanups);
- **stop when the requested task is complete**.

If a later task would be required to finish the current feature, **identify it** in the task summary as a
follow-up rather than implementing it automatically. Implement it as part of the current task only when
it is strictly necessary for the current task to work, and say so explicitly.

## 6. Type Safety

### TypeScript
- **Strict TypeScript is required.** Strict-family compiler options stay enabled; never weaken them
  (`strict: false`, blanket `// @ts-nocheck`, excluded files) to make code compile.
- **Do not use `any`.** Do not use unsafe casts (`as unknown as X`, `as any`, casting domain objects to
  force an assignment) as a way to avoid modelling the data.
- **All API responses must be typed.** Define a type for every payload the frontend consumes, and validate
  untrusted payloads at the boundary rather than asserting their shape.
- **No duplicated type definitions.** One canonical definition; import it instead of redeclaring a
  near-identical shape.
- If an unsafe type escape is genuinely unavoidable (for example an untyped third-party API), keep it
  local to the single boundary call, add a comment explaining **why**, and immediately convert the value
  into a typed structure. Escapes must not leak into application types.

### Python
- **Explicit typing for application code**: parameter and return annotations on functions, services, and
  models.
- **Prefer typed request/response models and typed service interfaces** (Pydantic models at boundaries;
  typed service signatures internally).
- **Avoid dynamically structured data where a clear schema is appropriate.** Do not pass
  `dict[str, Any]` or untyped dicts through layers when a model/interface belongs there.
- Validate incoming data with models rather than defensive `isinstance`/`get` chains.

## 7. API Standards (FastAPI)

Every endpoint must declare:

- **an explicit request model** for all input (body, query, path) — never hand-parsed JSON or raw `dict`
  payloads;
- **an explicit response model** (or an explicit no-body `204` response);
- **validation** performed through the model layer, not re-implemented ad hoc in the handler;
- **authentication and authorization requirements** (see §9), applied with deny-by-default defaults;
- **a thin route handler** that validates/maps and delegates to a service — no business logic hidden inside
  route handlers when it belongs in a service.

Status codes must be meaningful, not a blanket `200`/`500`:

| Case | Code |
|---|---|
| success with body | 200 |
| resource created | 201 |
| success, no body | 204 |
| malformed or invalid input | 422 (validation) / 400 |
| not authenticated | 401 |
| authenticated but not allowed | 403 |
| resource missing or not visible to this user | 404 |
| conflicting state (duplicate, already running, stale version) | 409 |
| limit/rate exceeded | 429 |
| unexpected internal failure | 500 |
| required dependency unavailable (provider/Hermes) | 502 / 503 |

- **Error responses are consistent:** a stable machine-readable code, a safe human-readable message, and a
  correlation/request id. No HTML error pages, no raw provider payloads, no SQL errors, no stack traces, no
  internal hostnames or file paths.
- **API contracts must be deliberate and stable.** Prefer additive change. A breaking contract change
  requires an explicit decision recorded in the task summary plus the corresponding frontend and
  documentation updates in the same change.
- **Do not expose database implementation details unnecessarily:** no ORM models, table/column names, SQL,
  migration internals, or internal identifiers belonging to other tenants.

## 8. Database Standards

- **Migrations are the source of truth for schema changes.** Every schema change ships as a migration in
  source control, reviewed like code. Never hand-edit a hosted schema for anything meant to persist, and
  never create or alter tables from application runtime code.
- **Database constraints should enforce important invariants:** required fields non-null, foreign keys for
  real references, uniqueness where duplicates are invalid, and check constraints for value domains.
  Prefer database-enforced correctness over hopeful application checks.
- **Indexes should be based on actual query patterns.** Add an index because a real query needs it, and
  name that query in the change description. No speculative indexes.
- **Ownership must be enforced.** Every user-owned row carries its owner reference, and every read and
  write is scoped to the authenticated owner — enforced in the API and in the database.
- **Row Level Security must be used where appropriate** for user data, and **not merely enabled**: write
  real, tested policies that fail closed (no permissive defaults, no unconditional `true` policies).
  Enabling RLS is not evidence of isolation until the policies are tested.
- **Users must never be able to access another user's data.** Any query path that could cross a tenant
  boundary is a defect, not an accepted limitation.
- **Do not create speculative tables or columns.** Schema is added for the requirement being implemented,
  not for anticipated future features.
- **Do not store sensitive secrets in ordinary application tables** (provider API keys, tokens,
  service-role credentials) unless it is explicitly required and the storage design is deliberate and
  secure.
- Store timestamps in UTC; localize only for display.

## 9. Authentication & Authorization

**Authentication is who the user is. Authorization is what that user is allowed to access or do.** They
are separate concerns: succeeding at one never implies the other.

- **Never rely solely on frontend checks.** Hiding a button or disabling a control is UX, not security.
- **All security-sensitive authorization decisions must ultimately be enforced server-side** — in the
  FastAPI layer — and, for user-data isolation, database-side through RLS policies (§8).
- **Deny by default.** A new endpoint or operation is forbidden until its authorization rule is explicit.
- Ownership is verified explicitly: load the resource, confirm the authenticated principal owns it, then
  act. Never accept an id from a client and mutate the resource behind it without that check.

**Never trust client-supplied values.** Each of these must be derived from the verified server-side
session or server-side records:

| Client-supplied value | Trusted source |
|---|---|
| user id / workspace id | authenticated session identity |
| ownership fields (`user_id`, `owner_id`, `workspace_id`) | server-side ownership lookup |
| credit balances or quota counters | server-side usage/ledger records |
| permission or role values | server-side records and configuration |
| payment/subscription status | verified server-side (payment-provider) records |
| agent capability/tool grants | server-side configuration |

## 10. Security Principles

- **Least privilege:** every process, worker, database role, token, and agent run receives the minimum
  access required — no shared superuser credentials across layers.
- **Deny-by-default access** for unknown actions, unknown resources, and unknown tools.
- **Secret isolation:** secrets live in environment/secret management (§16), never in source, prompts,
  logs, or client bundles.
- **Input validation:** validate everything at the API boundary (types, length, range, format, size), and
  treat user input, uploaded files, tool output, and model output as untrusted.
- **Safe file handling:** validate type and size before accepting, generate storage names server-side,
  never construct filesystem or storage paths from user input, normalize and confirm resolved paths stay
  inside their intended root (**path traversal protection**), and never serve from a user-named location.
- **Protection against unauthorized data access:** scope every query by owner; do not reveal the existence
  of another user's resource (prefer `404` to `403` where `403` would leak ownership).
- **Safe tool execution:** tools run with explicit permissions, no ambient credentials, and outside the API
  host. See §12.
- **Safe Hermes isolation:** Hermes runs in a separate execution environment with only the credentials
  needed for the current run, and with no access to AgentsChat service credentials or internal networks.

**Never expose to the browser:** Supabase service-role credentials, provider/API keys, private secrets,
internal infrastructure credentials, internal service URLs, or signing keys.

**Never log secrets.** Do not log tokens, credentials, or unnecessary sensitive user content (message
bodies, uploaded file contents, full prompts) — log identifiers, counts, and metadata instead. See §13.

## 11. Hermes Boundary

**Hermes is an execution dependency, not a library to be woven through the codebase.**

- **All communication with Hermes goes through an explicit adapter/interface** owned by AgentsChat. One
  boundary owns: invoking execution, passing the run's inputs and limits, receiving results/events, and
  translating failures into AgentsChat error types.
- **Do not allow Hermes-specific implementation details to leak throughout the codebase.** No Hermes
  imports, Hermes config keys, Hermes CLI flags, or Hermes response shapes outside that boundary.
- **AgentsChat business logic must be testable without a live Hermes runtime.** Unit tests of AgentsChat
  logic use a fake/stub adapter; only controlled integration tests touch a real Hermes environment, and
  those must not be part of the default fast test path (§14).
- **Verify, do not assume.** Confirm the actual installed Hermes version, its supported interfaces, and its
  conventions from the checked-out source before relying on behavior. Never invent function names, flags,
  config keys, or capabilities.
- **Prefer supported extension points** (documented CLI, skills, tools, plugins, MCP) over modifying Hermes
  core. Changing Hermes source requires an explicitly scoped task that names the Hermes area; never do it
  as a side effect of an AgentsChat change (see Appendix A).
- **The runtime must never bypass product controls.** Hermes execution may not circumvent AgentsChat
  authentication, authorization, tenant isolation, quota/usage limits, or approval requirements.

**Do not give agents unrestricted access to:**

- the host filesystem (or any path outside the run's isolated workspace),
- unrelated user data (another user's or workspace's records, files, or conversations),
- Supabase service-role credentials,
- internal secrets or infrastructure credentials,
- unrelated network resources (arbitrary egress, internal services, instance metadata endpoints).

## 12. Agent Safety & Resource Control

AgentsChat executes AI agents, so execution is the highest-risk operation in the product. Every execution
path must define and enforce:

- **Execution limits:** maximum steps/iterations, tool calls, tokens, and output size per run.
- **Timeouts:** a hard wall-clock limit; exceeding it terminates the run and records a terminal state.
- **Cancellation:** user-initiated and system-initiated cancellation that stops work and releases resources.
- **Retries:** bounded, with backoff, only for transient failures and only for operations safe to repeat
  (idempotent / deduplicated). No unbounded retry loops.
- **Tool permissions:** per-run allowlists driven by server-side configuration; consequential external
  actions (publishing, sending messages, purchasing, deleting, writing outside the run workspace) require
  explicit human approval.
- **Resource boundaries:** per-user/workspace quotas, concurrency caps, input/output size caps, and no shared
  mutable state or credentials between different users' runs.
- **Runaway execution prevention:** step/depth caps, no unbounded recursion, no self-restarting or
  self-scheduling runs, and a cost/usage ceiling that terminates the run.
- **Explicit execution states:** every run has a persisted, explicit state — `queued`, `running`,
  `completed`, `failed`, `cancelled` (and `needs_review` where review is part of the flow). Never infer
  state from the absence of a record or from a process still existing. A run is complete only when a
  terminal state is persisted and its result and usage are recorded.

**Explicitly prohibited:**

- **Unbounded recursive agent execution** (agent → sub-agent → sub-agent with no depth cap).
- **Arbitrary agent spawning.** Agents may spawn sub-agents only where an explicit product requirement
  exists, with a declared maximum fan-out, a depth limit, and a cost cap. Agent-to-agent spawning is a
  product decision, not an implementation detail.

## 13. Error Handling

Errors must be handled intentionally, by category — not by catching everything and returning a generic
failure:

| Category | Treatment |
|---|---|
| validation error | reject at the boundary with a specific, safe message (400/422); never reach business logic |
| authentication error | 401; do not reveal whether the account/resource exists |
| authorization error | 403 (or 404 when 403 would leak ownership); log the denial for audit |
| not-found | 404 with a safe message; never leak internal identifiers |
| conflict | 409; describe the conflicting state, not internal details |
| external-service failure | 502/503; safe user-facing message; record which dependency failed |
| transient failure | retry with bounded backoff only where the operation is safe to repeat |
| unexpected internal failure | 500; log full details server-side with a correlation id, return a generic message |

Rules:

- **Users receive useful but safe errors.** Say what they can do next (retry, fix input, contact support
  with the reference id) without exposing mechanics.
- **Never expose stack traces, SQL/database errors, provider raw payloads, internal hostnames, file paths,
  or secrets** to users or the browser.
- **Never swallow errors silently.** No bare `except: pass`, no empty `catch {}`, no success response after
  a failed step. Handle, translate, or re-raise with context.
- Log diagnostic detail server-side with the correlation/request id so a user-visible error can be traced.
- Preserve the distinction between "we did not do it", "we tried and it failed", and "it may have
  happened" — never report success for an operation whose outcome is unknown.

## 14. Testing Requirements

**Philosophy: tests verify behavior, not implementation trivia.** A test should fail when the product's
behavior breaks and survive a legitimate refactor. Snapshot-style assertions on internal structure, tests
that assert private helper calls, and tests written only to raise a coverage number are not acceptable.

**Every meaningful feature must include appropriate tests.** Required coverage areas:

- **API endpoints:** success, invalid input, unauthenticated, unauthorized, not-found, conflict, and
  unexpected-error paths.
- **Business logic:** the rules themselves, tested directly at the service layer.
- **Authorization:** explicit negative tests proving one user cannot read, modify, or delete another
  user's data (and that protected routes reject missing/invalid credentials).
- **Database behavior where practical:** constraints, migrations, and tenant isolation.
- **Critical UI behavior:** the paths users depend on (submitting input, rendering run status, showing
  errors and empty states) — tested at the component/integration level where practical.
- **Hermes adapter behavior:** request mapping, response mapping, and error translation against a fake
  Hermes runtime.
- **Execution lifecycle:** state transitions, cancellation, timeout, retry/idempotency, and recovery of
  runs that were left non-terminal.
- **Billing/credits when introduced:** balance changes, idempotency, and refusal when quota is exhausted.
- **Security boundaries:** path traversal, oversized/invalid file uploads, cross-tenant access attempts,
  and trust of client-supplied ids/ownership fields.

Rules:

- **Do not create meaningless tests** purely to increase a coverage percentage.
- Prefer deterministic fakes/stubs over live external calls; **never make live, billable model or provider
  calls in ordinary unit tests.**
- Every bug fix that changes behavior should come with a regression test.
- **Run the relevant test suite before declaring a task complete**, and report: the exact commands run,
  what passed, what failed, and anything not run (with the reason). Never claim a test passed when it was
  not executed.

## 15. Frontend Standards

- **Accessible:** semantic HTML first, keyboard operability, visible focus, labelled form controls, and
  sufficient contrast. Do not use a `div` where a `button`, `label`, or heading element is correct.
- **Responsive:** usable at small and large viewports; no fixed layouts that break on mobile.
- **Clear loading states:** users must see that work is in progress — and it must reflect reality (never
  show a step as complete before it is).
- **Clear error states:** every failure path has a visible, actionable message; no silent failures, no
  infinite spinners, no raw error objects rendered to users.
- **Empty states where appropriate:** a new user with no data should see guidance, not a blank region.
- **Maintainable component boundaries:** one responsibility per component; extract shared UI rather than
  copy-pasting markup; keep files and prop surfaces reasonably small.
- **No substantial business logic inside presentation components.** Data fetching, mutation, validation
  rules, and authorization expectations live in a data/API layer or the backend — components render state
  and emit events.
- **Do not introduce a global state library unless a demonstrated requirement exists.** Prefer local
  component state and server data; add a store only with a concrete, written need.
- **Do not over-engineer the component architecture.** No generic component framework, no premature
  design-system abstraction, no prop-drilling workarounds for a problem that does not exist yet.

## 16. Environment Variables

- **Secrets belong in environment variables / secret management**, never in source code, docs, prompt
  text, fixtures, or client bundles.
- **`.env.example` may contain variable names and safe placeholder examples** — it must never contain
  real credentials or production values.
- **Real secrets must never be committed.** Confirm `.env*` files are ignored before adding any.
- **Browser-exposed variables must be intentionally marked and intentional.** Only prefix a variable for
  client exposure when the value is genuinely public; **never expose service-role keys, provider API keys,
  signing keys, or server credentials to the browser**, regardless of prefixing.
- **Server-only secrets must never reach client bundles.** Do not import server-only modules into client
  components; verify that a server-only value is unavailable to the browser rather than assuming it.
- **Check whether a variable is actually required before introducing it.** No placeholder configuration for
  features that do not exist.
- Validate required configuration at startup (fail fast with a clear message naming the missing variable),
  rather than failing unpredictably at request time.

## 17. Dependencies

Before adding any dependency, answer all of these in the task/PR description:

1. **Is it actually necessary?** What requirement cannot be met without it?
2. **Can the requirement be solved with the existing stack?**
3. **Does it add significant complexity** (build steps, runtime services, config, mental model)?
4. **Is it maintained** (recent releases, responsive maintainers, active issue triage)?
5. **Does it introduce security or licensing concerns?** (transitive dependencies, advisories, license
   compatibility)
6. **Does it create infrastructure requirements?** (a new service, database, or environment — see §4)

- **Do not add libraries merely because they are popular.**
- **Prefer existing project capabilities** where reasonable.
- Prefer small, focused dependencies over large frameworks for a narrow need.
- Keep lockfiles updated in the same change that adds or updates a dependency.

## 18. Code Quality

Required:

- **Readable code** that a new engineer can follow without a walkthrough.
- **Small, focused functions** with a single clear responsibility.
- **Clear names** for functions, variables, files, and modules — no cryptic abbreviations.
- **Minimal duplication:** extract shared logic instead of copying it; three real repetitions is a signal.
- **Explicit boundaries** between layers (see §3) rather than convenience shortcuts.
- **Comments only where they explain non-obvious reasoning** (why a constraint exists, why an unusual
  workaround is required) — not restating what the code says.

Avoid:

- giant files and giant functions (if a file or function needs a table of contents, split it);
- **magic values** — name constants and explain their meaning;
- unnecessary abstractions (interfaces with one implementation, layers that only forward calls);
- premature generic frameworks built for imagined future requirements;
- dead code and unreachable branches;
- commented-out old implementations — delete them; version control is the history.

Keep error handling, logging, and validation consistent with the patterns already established in the
codebase rather than introducing a parallel style.

## 19. Git & Change Management

Agents must:

- **make focused changes** — one logical change per task/commit, matching the requested scope;
- **avoid unrelated formatting changes** (no whole-file reformats, no reordering imports across files you
  did not otherwise touch, no whitespace churn);
- **avoid modifying unrelated files** — touching a file means the task requires it;
- **inspect the diff before completion** (`git diff`, `git status`) and confirm it contains only intended
  changes;
- **never commit secrets** (keys, tokens, `.env` files, credentials in fixtures or logs);
- **never rewrite history** (rebase, amend, force-push, squash) unless explicitly instructed;
- **never claim** to have run commands, tests, builds, or deployments that were not actually run.

When a task is complete, the agent must be able to state clearly:

- **what changed** (files and behavior);
- **why it changed** (the requirement it satisfies);
- **what was tested** (exact commands and results) and what was **not** tested, with the reason;
- **whether anything remains** (known limitations, follow-up tasks, blockers).

## 20. Documentation

Update documentation when any of these change:

- **architecture** (component boundaries, execution flow, dependency direction);
- **environment variables** (names, meaning, required/optional, how to obtain them);
- **setup procedures** (local development, required tooling, first-run steps);
- **APIs** materially (new endpoints, changed contracts, breaking changes);
- **database architecture** (tables, ownership model, policies, migration procedure);
- **deployment procedures** (environments, services, release steps);
- **important engineering decisions** (a deliberate complexity addition, a contract change, a rejected
  alternative that will be questioned later).

Rules:

- **Do not create documentation that merely repeats obvious code.** Document intent, constraints,
  decisions, and procedures — not a narration of statements.
- Keep the relevant doc next to what it describes, and update it in the **same change** as the code.
- If setup or behavior changed, update the affected `.env.example` and setup instructions in the same task.

## 21. No Speculative Features

**Do not implement features merely because they may be useful later.** Unrequested functionality adds
maintenance cost, attack surface, and design debt, and it makes the review of the requested change harder.

Until the relevant development phase explicitly calls for them, do **not** implement:

- an agent marketplace
- organizations
- teams / multi-user collaboration
- advanced memory systems
- semantic search / embeddings
- billing and payments
- scheduling / recurring runs
- third-party integrations
- analytics dashboards
- complex multi-agent orchestration

The same prohibition applies to their scaffolding: no placeholder tables, no empty feature flags for
unbuilt features, no "v2" code paths, no interfaces defined only for an imagined future caller.

If the current task reveals that one of these is genuinely required, **stop and ask** — present the
requirement, why the current scope cannot be satisfied without it, and the smallest version that would
work. Do not decide it unilaterally.

## 22. Definition of Done

A task is complete **only** when, as applicable:

1. **Implementation is complete** — the requested behavior exists end to end.
2. **Requirements are satisfied** — the stated acceptance criteria are met, not approximately met.
3. **Type checking passes** (TypeScript strict; Python annotations/type checks where configured).
4. **Linting passes** where configured, without suppressing rules to hide problems.
5. **Relevant tests pass** — run, not assumed (§14), including the negative/authorization cases.
6. **Build succeeds** where applicable (frontend build, API import/startup check).
7. **Security implications have been considered** — authorization enforced, input validated, no secrets
   exposed or logged, no trust placed in client-supplied ownership/limits (§8–§11).
8. **No unrelated functionality was changed** — the diff contains only what the task required (§5, §19).
9. **Required documentation is updated** (§20).
10. **The final diff has been reviewed** and the summary states what changed, why, what was tested, and
    what remains.

**Then STOP.**

Completing a task does not authorize starting the next one. Do not continue into later roadmap items, do
not "prepare" future features, and do not fix unrelated issues you noticed — record them as follow-ups in
the summary instead.

---

## Appendix A — Hermes Runtime Source in This Checkout

The Hermes agent runtime is present in this repository as upstream source. It is an **execution
dependency** of AgentsChat, not part of the AgentsChat application.

- **Read the area guide before editing an area:** `agent/AGENTS.md`, `hermes_cli/AGENTS.md`,
  `gateway/AGENTS.md`, `tools/AGENTS.md`, `plugins/AGENTS.md`, `skills/AGENTS.md`, `cron/AGENTS.md`,
  `tui_gateway/AGENTS.md`, `web/AGENTS.md`, `apps/desktop/AGENTS.md` (+ `apps/desktop/src/AGENTS.md`).
- **Preserve upstream Hermes conventions in Hermes source.** Do not carry AgentsChat conventions into
  Hermes source, and do not carry Hermes runtime conventions into AgentsChat application code.
- **Hermes tests run through `scripts/run_tests.sh`**, never a bare `pytest` invocation (it sets up the
  isolated test environment). AgentsChat tests use the tooling configured when the AgentsChat application
  is created.
- **Prefer supported extension points** (CLI commands, skills, tools, plugins, MCP) over modifying Hermes
  core. A Hermes source change requires an explicitly scoped task that names the area; never make one as a
  side effect of an AgentsChat change.
- **`web/` in this checkout is Hermes's dashboard SPA** (it embeds the real TUI). It is **not** the
  AgentsChat Next.js application. Never use it as the frontend for AgentsChat.
- If Hermes's behavior must be relied upon, verify it against the checked-out source and version rather
  than from documentation or memory.
