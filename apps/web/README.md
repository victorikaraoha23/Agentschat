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
