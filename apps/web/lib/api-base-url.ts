/**
 * Base URL of the AgentsChat API as seen from the browser.
 *
 * Single place that reads the public variable (Task 1.5), so every API module
 * agrees on the same base URL and the environment is read once. It is public
 * by necessity — `NEXT_PUBLIC_*` values are compiled into the client bundle —
 * so it must never hold a secret (root AGENTS.md §16).
 */

export const API_BASE_URL: string =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
