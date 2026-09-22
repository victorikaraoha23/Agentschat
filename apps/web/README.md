# AgentsChat web application

The AgentsChat web application: Next.js (App Router), React, TypeScript in strict mode. It is the
frontend of the product and, per the root `AGENTS.md`, communicates with the AgentsChat API only.

**Status: foundation only.** A single static page proves that the app builds and renders. There is no
chat, authentication, API client, data fetching, or agent integration yet.

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

## Note on npm workspaces

This app is an **independent** package even though `apps/` is matched by the Hermes runtime's root
`package.json` workspace glob (`apps/*`). Install with `npm install --workspaces=false` so npm keeps this
app out of the Hermes monorepo's JavaScript workspace and does not pull in the runtime's own JS
dependencies. `node_modules/` and `package-lock.json` live inside `apps/web/`.

## Structure

```text
apps/web/
├── app/            # App Router: layout, page, global styles
├── public/         # static assets served at /
├── AGENTS.md       # framework-generated Next.js agent rules; the root AGENTS.md governs
└── package.json    # independent package: agentschat-web
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
- **Imports.** Use the `@/*` alias (it maps to `apps/web/*`) for cross-folder imports and relative paths
  inside a folder: `import { CopyButton } from "@/components/copy-button";`.
- **TypeScript.** `strict` stays enabled: no `any`, no unsafe casts, explicit prop types
  (root `AGENTS.md` §6).
- **Naming.** Reserved Next.js files stay lowercase (`page.tsx`, `layout.tsx`); every other file is
  kebab-case. Exported components, types and interfaces are PascalCase.
- **Formatting.** Match the surrounding style. No formatter is configured yet — deliberately deferred.

Anything not covered here follows the root `AGENTS.md`, which governs this code.
