import assert from "node:assert/strict";
import { test } from "node:test";

// No NEXT_PUBLIC_SUPABASE_* variables are set in this process (node --test
// isolates files in separate processes), so the client must be unavailable.
const { getSupabaseClient, isSupabaseConfigured } = await import("./supabase-client.ts");

test("reports unconfigured and returns null when variables are absent", () => {
  assert.equal(process.env.NEXT_PUBLIC_SUPABASE_URL, undefined);
  assert.equal(process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY, undefined);
  assert.equal(isSupabaseConfigured(), false);
  assert.equal(getSupabaseClient(), null);
});
