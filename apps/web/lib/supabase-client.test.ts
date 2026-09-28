import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

function readOwnSource(): Promise<string> {
  return readFile(new URL("./supabase-client.ts", import.meta.url), "utf8");
}

process.env.NEXT_PUBLIC_SUPABASE_URL = "https://example.supabase.co";
process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = "test-anon-key";

const { getSupabaseClient, isSupabaseConfigured } = await import("./supabase-client.ts");

test("initializes a browser client from the public URL and anon key", async () => {
  assert.equal(isSupabaseConfigured(), true);

  const client = getSupabaseClient();

  assert.ok(client, "expected a client when both variables are set");
  // The browser client is built from exactly the public pair — assert on the
  // module's own variable surface, not the SDK's internals: no privileged
  // variable name may exist in this module, so none can reach the browser bundle.
  // (The word "secret" alone appears in benign prose, so check full names.)
  const source = await readOwnSource();
  assert.match(source, /NEXT_PUBLIC_SUPABASE_URL/);
  assert.match(source, /NEXT_PUBLIC_SUPABASE_ANON_KEY/);
  for (const forbidden of ["SERVICE_ROLE", "service_role", "service-role", "PRIVATE_KEY", "SUPABASE_PASSWORD"]) {
    assert.equal(source.includes(forbidden), false);
  }
});

test("returns the shared client on repeated calls", () => {
  assert.equal(getSupabaseClient(), getSupabaseClient());
});
