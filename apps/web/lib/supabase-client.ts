/**
 * Browser-safe Supabase client — the only Supabase entry point the web app
 * uses (Task 3.1: connectivity boundary only; no auth, no queries, no tables).
 *
 * Centralized here so future callers import this module instead of creating
 * their own clients. Uses ONLY the public project URL and anon key: both are
 * `NEXT_PUBLIC_*` (compiled into the browser bundle by necessity) and must
 * never hold a privileged credential — the backend's private access token
 * stays server-side in the API and has no corresponding variable here.
 *
 * When either variable is absent the client cannot be created: `null` is
 * returned and the app runs without Supabase rather than pretending a
 * connection exists. There is no logging here — production console output
 * stays quiet (Task 2.3 decision) and credential material must never reach a log.
 */

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const SUPABASE_URL: string | undefined = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_ANON_KEY: string | undefined = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

let cachedClient: SupabaseClient | null = null;
let cachedFrom: { url: string; key: string } | null = null;

/**
 * Return the shared browser Supabase client, or `null` when unconfigured.
 * Construction only — no network call, no auth flow, no query.
 */
export function getSupabaseClient(): SupabaseClient | null {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
    return null;
  }
  if (cachedFrom?.url !== SUPABASE_URL || cachedFrom?.key !== SUPABASE_ANON_KEY) {
    cachedClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
    cachedFrom = { url: SUPABASE_URL, key: SUPABASE_ANON_KEY };
  }
  return cachedClient;
}

/** Whether the browser Supabase pair is present (both or neither). */
export function isSupabaseConfigured(): boolean {
  return Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);
}
