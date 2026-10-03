/**
 * Shell access decision for the authenticated application area (Task 4.1).
 *
 * A pure function of the `SessionState` that `lib/auth.ts` already reports:
 * it maps session truth to one of three shell views — loading, granted, or
 * denied — so the guard component owns no authentication judgment of its own
 * and there is no second authentication system. Supabase is never touched
 * here; the caller resolves the session through the established boundary.
 *
 * The navigation model beside it is deliberately the smallest set the current
 * application needs (home + sign out). New entries appear only when the task
 * that builds the corresponding feature adds them.
 */

import type { SessionState } from "./auth.ts";

/** What the authenticated shell shows for a given session state. */
export type ShellAccess =
  | { view: "loading" }
  | { view: "granted"; userId: string; email: string | null }
  | { view: "denied"; reason: "unauthenticated" | "unconfigured" | "unreadable" };

/**
 * Decide which shell view a session state maps to.
 *
 * - `null` (still resolving) → loading; nothing private renders yet.
 * - `authenticated` → granted, carrying the caller's identity forward.
 * - `unauthenticated` → denied as unauthenticated.
 * - `unconfigured` → denied as unconfigured (same denial, honest reason).
 * - `error` → denied as unreadable.
 */
export function toShellAccess(session: SessionState | null): ShellAccess {
  if (session === null) {
    return { view: "loading" };
  }
  if (session.status === "authenticated") {
    return { view: "granted", userId: session.userId, email: session.email };
  }
  if (session.status === "unauthenticated") {
    return { view: "denied", reason: "unauthenticated" };
  }
  if (session.status === "unconfigured") {
    return { view: "denied", reason: "unconfigured" };
  }
  return { view: "denied", reason: "unreadable" };
}

/** A shell navigation entry: where it goes and what it says. */
export interface ShellNavEntry {
  href: string;
  label: string;
}

/**
 * The shell's navigation. Two entries only: the public home (an explicit way
 * back out of the authenticated area) and the shell root itself. Future tasks
 * add entries when their features exist — never in advance.
 */
export const SHELL_NAV: readonly ShellNavEntry[] = [
  { href: "/", label: "Home" },
  { href: "/app", label: "App" },
];
