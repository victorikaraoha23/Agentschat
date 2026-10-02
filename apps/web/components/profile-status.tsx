"use client";

import { useEffect, useState } from "react";

import { fetchMyProfile, type ProfileResult } from "@/lib/profile-api";

/**
 * Confirms, for a signed-in user, that the API can resolve their AgentsChat
 * profile (`GET /me`). Deliberately a single line of confirmation — not a
 * profile page.
 *
 * The parent renders this only when a session exists, and `fetchMyProfile`
 * resolves the token itself, so nothing is requested without one: no profile
 * data can reach a signed-out view.
 */
export function ProfileStatus() {
  const [result, setResult] = useState<ProfileResult | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetchMyProfile().then((next) => {
      if (!cancelled) {
        setResult(next);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <p className="status-line">
      AgentsChat profile:{" "}
      {result === null ? (
        <span className="status-pending">checking…</span>
      ) : result.ok ? (
        <span className="status-ok">resolved for your account</span>
      ) : (
        <span className="status-error">{result.message}</span>
      )}
    </p>
  );
}
