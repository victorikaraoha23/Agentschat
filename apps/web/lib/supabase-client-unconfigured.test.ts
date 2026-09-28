import assert from "node:assert/strict";
import { test } from "node:test";

// Clear inherited values before the module captures its configuration.
// node --test isolates files in separate processes.
delete process.env.NEXT_PUBLIC_SUPABASE_URL;
delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

const { getSupabaseClient, isSupabaseConfigured } = await import("./supabase-client.ts");

test("reports unconfigured and returns null when variables are absent", () => {
  assert.equal(process.env.NEXT_PUBLIC_SUPABASE_URL, undefined);
  assert.equal(process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY, undefined);
  assert.equal(isSupabaseConfigured(), false);
  assert.equal(getSupabaseClient(), null);
});
