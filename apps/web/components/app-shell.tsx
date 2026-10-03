"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { ProfileStatus } from "@/components/profile-status";
import { getCurrentSession, signOut, type SessionState } from "@/lib/auth";
import { SHELL_NAV, toShellAccess } from "@/lib/shell-access";

const DENIED_MESSAGES = {
  unauthenticated: "Sign in to open the application shell.",
  unconfigured: "Authentication is not configured, so the application shell is unavailable.",
  unreadable: "Your session could not be read: sign in again.",
} as const;

/**
 * The authenticated application shell: minimal chrome around future product
 * content (Task 4.1).
 *
 * Access is decided by `toShellAccess` over the session `lib/auth.ts`
 * reports — the same boundary every other page uses, so there is no second
 * authentication system. While the session resolves the shell shows a loading
 * state and **no private content**; a denied session sees only the denial and
 * a link out. A granted session sees the shell header (brand, navigation,
 * sign-out) and the page content below it.
 */
export function AppShell() {
  const [session, setSession] = useState<SessionState | null>(null);
  const [signOutError, setSignOutError] = useState<string | null>(null);
  const [signingOut, setSigningOut] = useState(false);
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;
    void getCurrentSession().then((next) => {
      if (!cancelled) {
        setSession(next);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSignOut = useCallback(async () => {
    setSigningOut(true);
    setSignOutError(null);
    const result = await signOut();
    if (result.ok) {
      setSession(await getCurrentSession());
      router.refresh();
    } else {
      setSignOutError(result.message);
    }
    setSigningOut(false);
  }, [router]);

  const access = toShellAccess(session);

  if (access.view === "loading") {
    return (
      <div aria-live="polite">
        <p className="status-line">
          <span className="status-pending">Loading…</span>
        </p>
      </div>
    );
  }

  if (access.view === "denied") {
    return (
      <div aria-live="polite">
        <p className="status-line">
          <span className="status-error">{DENIED_MESSAGES[access.reason]}</span>
        </p>
        <p className="muted">
          <Link href="/login">Sign in</Link> or <Link href="/">back to the home page</Link>.
        </p>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="app-shell-header surface">
        <p className="status-line app-shell-brand">AgentsChat</p>
        <nav aria-label="Application">
          <ul className="shell-nav">
            {SHELL_NAV.map((entry) => (
              <li key={entry.href}>
                <Link href={entry.href}>{entry.label}</Link>
              </li>
            ))}
          </ul>
        </nav>
        <p className="status-line">
          <span className="status-ok">Signed in{access.email !== null ? ` as ${access.email}` : ""}</span>
        </p>
        <button type="button" onClick={handleSignOut} disabled={signingOut}>
          {signingOut ? "Signing out…" : "Sign out"}
        </button>
        {signOutError !== null && (
          <p className="status-error" role="alert">
            Sign out failed — {signOutError}
          </p>
        )}
      </header>
      <section aria-label="Application content" className="surface app-shell-content">
        <p className="muted">
          This is the authenticated application shell. Product features will live here; today it only
          confirms who is signed in.
        </p>
        <ProfileStatus />
      </section>
    </div>
  );
}
