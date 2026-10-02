"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { getCurrentSession, signOut, type SessionState } from "@/lib/auth";
import { ProfileStatus } from "@/components/profile-status";

/**
 * Shows whether this browser has a session and lets a signed-in user sign out.
 *
 * Session state comes from `lib/auth.ts` (which reads the session Supabase
 * persists) — this component never touches the provider or a token. When a
 * session exists, the profile confirmation below it runs once.
 */
export function AuthStatus() {
  const [state, setState] = useState<SessionState | null>(null);
  const [signOutError, setSignOutError] = useState<string | null>(null);
  const [signingOut, setSigningOut] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void getCurrentSession().then((next) => {
      if (!cancelled) {
        setState(next);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const refresh = useCallback(async () => {
    setState(await getCurrentSession());
  }, []);

  async function handleSignOut() {
    setSigningOut(true);
    setSignOutError(null);
    const result = await signOut();
    if (result.ok) {
      await refresh();
    } else {
      setSignOutError(result.message);
    }
    setSigningOut(false);
  }

  return (
    <div aria-live="polite">
      <p className="status-line">
        Account:{" "}
        {state === null ? (
          <span className="status-pending">checking…</span>
        ) : state.status === "authenticated" ? (
          <span className="status-ok">
            signed in as {state.email ?? state.userId}
          </span>
        ) : state.status === "unauthenticated" ? (
          <span className="status-pending">not signed in</span>
        ) : state.status === "unconfigured" ? (
          <span className="status-pending">authentication not configured</span>
        ) : (
          <span className="status-error">{state.message}</span>
        )}
      </p>
      {state !== null && state.status === "authenticated" && (
        <>
          <ProfileStatus />
          <button type="button" onClick={handleSignOut} disabled={signingOut}>
            {signingOut ? "Signing out…" : "Sign out"}
          </button>
        </>
      )}
      {state !== null && state.status === "unauthenticated" && (
        <p className="muted">
          <Link href="/login">Sign in</Link> or <Link href="/signup">create an account</Link>.
        </p>
      )}
      {signOutError !== null && (
        <p className="status-error" role="alert">
          Sign out failed — {signOutError}
        </p>
      )}
    </div>
  );
}
