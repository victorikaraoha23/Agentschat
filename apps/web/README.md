# AgentsChat web application

The AgentsChat web application: Next.js (App Router), React, TypeScript in strict mode. It is the
frontend of the product and, per the root `AGENTS.md`, communicates with the AgentsChat API only.

**Status: foundation only.** The app proves itself end to end: the public home page requests `GET /health`
from the browser, `/signup` + `/login` create and use a Supabase Auth session (signup, sign in, sign
out, session detection), and the authenticated shell at `/app` confirms who is signed in and that the
API resolves their AgentsChat profile (`GET /me`). There is still no chat, no agent integration, no
profile page, and no database query from the browser — accounts are authentication plus this single
confirmation.

## Commands

Run from `apps/web/`:

| Command | Purpose |
|---|---|
| `npm install --workspaces=false` | Install dependencies (see the workspace note below) |
| `npm run dev` | Development server on <http://localhost:3000> |
| `npm run build` | Production build |
| `npm run start` | Serve the production build |
| `npm run lint` | ESLint (`eslint.config.mjs`, `eslint-config-next`) |
| `npm run typecheck` | `next typegen && tsc --noEmit` |
| `npm test` | Node's built-in test runner (`node --test`) for the API-request, auth, and profile modules |

## Configuration

Three optional, **client-visible** variables — never put a secret in any of them, because `NEXT_PUBLIC_*`
values are compiled into the browser bundle (`apps/web/.env.example` documents them):

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://127.0.0.1:8000` | Base URL of the AgentsChat API as seen from the browser |
| `NEXT_PUBLIC_SUPABASE_URL` | *(unset)* | Supabase project URL (public identifier, browser-safe); when unset the client is unavailable |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | *(unset)* | Supabase anonymous/public key (browser-safe by design) — never a privileged key; when unset the client is unavailable |

No `.env` file is needed: the defaults run locally without Supabase. The app reaches the API through
three small modules — `app/health-api.ts` (`GET /health`), `lib/profile-api.ts` (`GET /me`), and
`lib/conversations-api.ts` (`POST /conversations`) — each of which builds the request URL from
`lib/api-base-url.ts`, applies a five-second deadline, checks the HTTP status, validates the response
shape and returns a typed result. Failures are categorised so the UI can tell them
apart: `network` (unreachable or timed out), `http` (non-success status, reported by status code only),
`invalid-response` (malformed body or unexpected shape) and `unexpected` (anything else). The message shown
to users is always these modules' own text — never a raw server body, stack trace, or error object — and the
functions never throw, so a misbehaving API produces a visible failure state instead of crashing the page.

## Supabase

The browser client lives in `lib/supabase-client.ts` (`getSupabaseClient` / `isSupabaseConfigured`): one
shared client built from the **public URL + anon key** — no privileged credential, no `NEXT_PUBLIC_*`
variable that could leak one. It returns `null` when either variable is unset, so the app still runs and
authentication simply reports itself unavailable.

## Authentication

Email/password signup, sign-in, sign-out, session detection, and the `GET /me` profile check through
Supabase Auth. No OAuth, no password reset, no email-verification screen, and no profile page. The
authenticated shell at `/app` reuses the same session boundary to decide access: while the session
resolves it shows only a loading state (never private content), an unauthenticated, unconfigured, or
unreadable session sees only a denial with a way back out, and a signed-in session sees the shell
header (brand, navigation, sign-out) with the profile confirmation below.

- `lib/auth.ts` is the only module that talks to Supabase Auth: `signUpWithEmail`, `signInWithEmail`,
  `signOut`, `getCurrentSession`, `getAccessToken`. Pages and components never touch the SDK, and
  `getAccessToken` hands a token straight to the one request needing it — the module never stores,
  caches, or renders an access token.
- `/signup` and `/login` render `components/auth-form.tsx` (email, password, submit, inline
  success/error state); the home page renders `components/auth-status.tsx`, which shows the session state
  and signs out.
- Sessions are Supabase's own: `getSession()` reads the session the SDK persists in the browser and
  refreshes it. This app adds no token handling, no cookie, and no session store.
- Every function returns a typed result with a fixed message of our own; provider error text never reaches
  the UI. Signup that still needs email confirmation is reported as `confirmation-required` — not as a
  signed-in user. `getCurrentSession` separates `unconfigured` and `error` from `unauthenticated`, so a
  broken check never looks like "signed out".
- None of this is authorization: the API's authenticated endpoints (`GET /me`, which proves the identity →
  profile bridge, and `POST /conversations`, which creates a row the caller owns) decide everything
  themselves, and the browser decides nothing about what a user may do.

## Conversation creation

`lib/conversations-api.ts` (`createConversation`, Task 5.2) posts `{title?}` to `POST /conversations`
with the session's bearer token — never a user id, because the API derives ownership from the token
it verifies. Results are typed (`unauthenticated` / `invalid-input` / `network` / `http` /
`invalid-response` / `unexpected`) with fixed messages; raw bodies never reach the UI. No product UI
uses it yet — it exists so tests and the next tasks have a typed creation path.

## Profile check

`lib/profile-api.ts` calls `GET /me` with the session's bearer token — **never a user id**, because the API
derives the identity from the token it verifies — and maps the answer to a typed result. A signed-in user's
account section renders `components/profile-status.tsx`, a single "resolved for your account" line (or a
fixed failure message); it is mounted only while a session exists, so no profile data can appear in a
signed-out view.

## Design foundation

`app/globals.css` holds the whole visual system (Task 4.2) — no framework, no component library:

- **Tokens.** Typography (`--font-sans`, base/sm/lg/xl sizes, body/heading line heights, three weights),
  spacing (`--space-xs`…`--space-2xl`), semantic colors (`--background`, `--foreground`, `--muted`,
  `--surface`, `--border`, `--primary` + `--primary-hover` + `--primary-foreground`, `--ok`, `--error`,
  `--focus`, each with a dark-mode value), and shape/depth/motion (`--radius-sm/md`, `--shadow-sm`,
  `--transition-fast`, `--content-max-width: 42rem`, `--control-height: 2.5rem`).
- **Elements.** Box sizing, body background/type/color, heading hierarchy, link color + hover, a `.surface`
  card primitive (surface background, border, radius, shadow), primary-action buttons with hover/disabled
  states, font-inheriting inputs, a 2px `--focus` focus-visible ring, and a reduced-motion block that
  disables transitions and animations.
- **Responsive.** The shell header stacks on narrow screens and spreads out past `40rem`; grids and flex
  wrap do the rest — no breakpoints file, no device detection.

`components/auth-form.module.css` is the only scoped stylesheet; it now reads the same tokens (surface
inputs, `--border` borders, `--control-height` targets, hover border, token transition). Everything else
is element styles plus the `.surface`, `.shell-nav`, and `.app-shell*` classes the shell uses.

### Contrast baseline

| Pair | Light | Dark | Use |
|---|---|---|---|
| foreground on background | 18.5 | 17.6 | body text |
| muted on background | 6.4 | 7.8 | secondary text, hints |
| primary on background | 4.6 | 6.3 | links |
| primary-foreground on primary | 4.6 | 5.1 | buttons |
| ok / error on background | 5.1 / 6.6 | 7.7 / 7.8 | status text |

Values are relative-luminance ratios from the hex pairs in `globals.css` (WCAG AA for normal text is
4.5; muted secondary text clears it in both modes).

## Note on npm workspaces

This app is an **independent** package even though `apps/` is matched by the Hermes runtime's root
`package.json` workspace glob (`apps/*`). Install with `npm install --workspaces=false` so npm keeps this
app out of the Hermes monorepo's JavaScript workspace and does not pull in the runtime's own JS
dependencies. `node_modules/` and `package-lock.json` live inside `apps/web/`.

## Deploying to Vercel

The Vercel project must point at this directory:

- **Root Directory** (Vercel project setting): `apps/web` — the repository root belongs to the Hermes
  runtime, not this application. This setting lives in the Vercel dashboard, so it cannot be versioned
  here; everything that *can* be versioned is.
- **Install command** (pinned in `vercel.json`): `npm install --workspaces=false`. Without the flag, npm
  treats this directory as a member of the Hermes root workspace (its `apps/*` glob) and installs the
  runtime's JavaScript dependency tree instead of this app's — verified with a local dry run.

Everything else uses Vercel's Next.js defaults: the build command is `npm run build` and the framework
handles the build output. Next 16 requires Node `>=20.9.0`, which Vercel's default Node version satisfies.
For the health check to work on Vercel, set `NEXT_PUBLIC_API_URL` to a public API URL in the Vercel build
environment and add the deployed web origin to the API CORS allowlist. The `127.0.0.1` default is for local
development only; it cannot reach the API from a deployed browser. The API currently allows development
origins only, so its production CORS configuration must be added before this integration is available on
Vercel.

## Analytics and Speed Insights

The root layout renders Vercel's **Web Analytics** (`@vercel/analytics`) and **Speed Insights**
(`@vercel/speed-insights`) — first-party telemetry for traffic and real-user performance. These are part of
the deployment story rather than new infrastructure: no server, database, queue, credential, or environment
variable is involved, and both packages are Vercel's official Next.js integrations.

How they behave (read from the installed packages' source, not assumed):

| Context | Behavior |
|---|---|
| On a Vercel deployment | Reports, using the platform-served `/_vercel/insights/script.js` and `/_vercel/speed-insights/script.js`. Enable both features in the project's Analytics and Speed Insights tabs; no code or environment change is needed |
| `npm run dev` | Loads the vendor's *debug* script, which prints events to the browser console instead of reporting them |
| Local `npm run build` + `npm start` | Those `/_vercel/...` paths do not exist locally, so the script fails to load and the package logs a console message. The application itself is unaffected |

Both are client components that render `null` and inject their script in an effect, which is why the tags
never appear in prerendered HTML. No page needs `"use client"` because of them.

**Consent and privacy handling is not implemented** — no cookie banner and no `beforeSend` filtering. That
belongs to the task that introduces user accounts and states the privacy requirements.

## Structure

```text
apps/web/
├── app/
│   ├── layout.tsx          # root layout: metadata, styles, Vercel telemetry
│   ├── page.tsx            # landing page: API health check + account status
│   ├── login/
│   │   └── page.tsx        # sign-in page
│   ├── signup/
│   │   └── page.tsx        # account-creation page
│   ├── globals.css         # application-wide styles
│   ├── health-api.ts       # calls GET /health and returns a typed result
│   └── health-api.test.ts  # node:test coverage for that module
├── components/
│   ├── auth-form.tsx            # shared email/password form (signup + login)
│   ├── auth-form.module.css     # scoped styles for that form
│   ├── auth-status.tsx          # session state display and sign-out button
│   └── profile-status.tsx       # one-line profile confirmation (signed-in only)
├── lib/
│   ├── api-base-url.ts          # the single read of NEXT_PUBLIC_API_URL
│   ├── auth.ts                  # the only module that talks to Supabase Auth
│   ├── auth.test.ts             # node:test coverage for that module
│   ├── profile-api.ts           # calls GET /me with the session's token
│   ├── profile-api.test.ts      # node:test coverage for that module
│   ├── supabase-client.ts       # browser Supabase client (public URL + anon key only)
│   ├── supabase-client.test.ts  # node:test coverage for that module
│   └── supabase-client-unconfigured.test.ts
├── public/                 # static assets served at /
├── .env.example            # documents NEXT_PUBLIC_* (public values only, no secrets)
├── vercel.json             # pins the install command for Vercel
├── AGENTS.md               # framework-generated Next.js agent rules; the root AGENTS.md governs
└── package.json            # independent package: agentschat-web
```

Directories are added when the code that needs them appears, not in advance. `lib/` arrived with the
Supabase browser client (its first shared module), and `components/` arrived with the shared
authentication form. There is no `hooks/`, `services/` or `features/` directory today because nothing
belongs in them yet.

## Conventions

Next.js conventions apply. These are the only project-specific rules on top of them.

- **Routes and layouts.** Routes live under `app/`, one folder per URL segment, using the reserved file
  names (`page.tsx`, `layout.tsx`, and later `loading.tsx` / `error.tsx` / `not-found.tsx` when a route
  actually needs them). A nested `layout.tsx` is added when routes genuinely share chrome, not in advance.
- **Server components first.** A component is a server component unless it needs browser interactivity, and
  `"use client"` is added to the smallest component that requires it — never to a whole route by default.
- **Styling.** Application-wide styles live in `app/globals.css`, imported once by the root layout.
  Component- or page-scoped styles use CSS Modules (`*.module.css`) colocated with the component. No CSS
  framework, design system, or component library is in use.
- **Reusable components.** When a component is used in more than one place it goes in
  `apps/web/components/`, as a kebab-case file exporting a PascalCase component (`copy-button.tsx` →
  `CopyButton`). A single-use component stays next to the page that uses it until it is genuinely shared.
- **Shared utilities.** Framework-agnostic helpers used more than once go in `apps/web/lib/`. Nothing that
  belongs to the API, the database, or a secret may end up in the browser bundle. The Supabase browser
  client lives there because it will be shared; it carries only the public URL + anon key.
- **Calling the API.** Browser requests go through small modules (`app/health-api.ts`,
  `lib/profile-api.ts`): the platform `fetch`, an HTTP-status check, response-shape validation, and a typed
  result instead of a thrown error. No HTTP library, and no abstraction layer for endpoints that do not
  exist yet.
- **Supabase.** The browser client lives in `lib/supabase-client.ts` and uses only the public URL + anon
  key (`getSupabaseClient` returns `null` when unconfigured). All Supabase Auth calls live in
  `lib/auth.ts` and nowhere else: pages and components call its typed functions (which never throw and
  never surface provider text) instead of the SDK. Supabase's own session storage is used — no session
  context and no route guard; the one deliberate token read is `getAccessToken`, which returns the token
  for a single request without storing, caching, or rendering it.
- **Imports.** Use the `@/*` alias (it maps to `apps/web/*`) for cross-folder imports and relative paths
  inside a folder (`@/components/auth-form`, `./health-api`). One exception: modules under `lib/` (and
  `app/health-api.ts` importing into `lib/`) use an explicit `.ts` extension (`./supabase-client.ts`),
  because Node's test runner resolves the exact specifier while `tsconfig.json`'s
  `allowImportingTsExtensions` keeps the bundler happy.
- **TypeScript.** `strict` stays enabled: no `any`, no unsafe casts, explicit prop types
  (root `AGENTS.md` §6).
- **Naming.** Reserved Next.js files stay lowercase (`page.tsx`, `layout.tsx`); every other file is
  kebab-case. Exported components, types and interfaces are PascalCase.
- **Formatting.** Match the surrounding style. No formatter is configured yet — deliberately deferred.

Anything not covered here follows the root `AGENTS.md`, which governs this code.
