# AgentsChat web application

The AgentsChat web application: Next.js (App Router), React, TypeScript in strict mode. It is the
frontend of the product and, per the root `AGENTS.md`, communicates with the AgentsChat API only.

**Status: foundation only.** One page proves that the app builds, renders, and can call the API: it requests
`GET /health` from the browser and reports whether the backend answered. There is no chat, authentication,
or agent integration yet, and no other API call exists.

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
| `npm test` | Node's built-in test runner (`node --test`) for the API-request module |

## Configuration

One optional, **client-visible** variable — never put a secret in it, because `NEXT_PUBLIC_*` values are
compiled into the browser bundle (`apps/web/.env.example` documents it):

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://127.0.0.1:8000` | Base URL of the AgentsChat API as seen from the browser |

No `.env` file is needed: the default is the local API. The page reaches the API only through
`app/health-api.ts`, which builds the request URL, checks the HTTP status, validates the response shape and
returns a typed result. It never throws, so an unreachable or misbehaving API produces a visible failure
state instead of crashing the page.

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
│   ├── page.tsx            # landing page: renders and reports the API health check
│   ├── globals.css         # application-wide styles
│   ├── health-api.ts       # calls GET /health and returns a typed result
│   └── health-api.test.ts  # node:test coverage for that module
├── public/                 # static assets served at /
├── .env.example            # documents NEXT_PUBLIC_API_URL (no secrets)
├── vercel.json             # pins the install command for Vercel
├── AGENTS.md               # framework-generated Next.js agent rules; the root AGENTS.md governs
└── package.json            # independent package: agentschat-web
```

Directories are added when the code that needs them appears, not in advance. There is no `components/`,
`lib/`, `hooks/`, `services/` or `features/` directory today because nothing belongs in them yet.

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
  belongs to the API, the database, or a secret may end up in the browser bundle.
- **Calling the API.** Browser requests go through a small colocated module (`app/health-api.ts`): the
  platform `fetch`, an HTTP-status check, response-shape validation, and a typed result instead of a thrown
  error. No HTTP library, and no abstraction layer for endpoints that do not exist yet.
- **Imports.** Use the `@/*` alias (it maps to `apps/web/*`) for cross-folder imports and relative paths
  inside a folder: `import { CopyButton } from "@/components/copy-button";`.
- **TypeScript.** `strict` stays enabled: no `any`, no unsafe casts, explicit prop types
  (root `AGENTS.md` §6).
- **Naming.** Reserved Next.js files stay lowercase (`page.tsx`, `layout.tsx`); every other file is
  kebab-case. Exported components, types and interfaces are PascalCase.
- **Formatting.** Match the surrounding style. No formatter is configured yet — deliberately deferred.

Anything not covered here follows the root `AGENTS.md`, which governs this code.
