/**
 * Unit tests for the authentication boundary (Task 3.2).
 *
 * Supabase is faked through the module's `AuthClientLike` seam, so no test
 * touches the live service. `node --test` runs each file in its own process,
 * so no NEXT_PUBLIC_SUPABASE_* variable is set here — the default client is
 * therefore unconfigured, which the last test asserts.
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  getCurrentSession,
  signInWithEmail,
  signOut,
  signUpWithEmail,
  type AuthClientLike,
  type ClientAuthResultLike,
} from "./auth.ts";

const USER = { id: "user-1", email: "person@example.com" };

function authResult(
  overrides: Partial<ClientAuthResultLike>,
): ClientAuthResultLike {
  return {
    data: { user: USER, session: { user: USER } },
    error: null,
    ...overrides,
  };
}

interface FakeCalls {
  signUp: { email: string; password: string } | null;
  signIn: { email: string; password: string } | null;
  signOut: number;
}

function fakeClient(options: {
  signUp?: ClientAuthResultLike;
  signIn?: ClientAuthResultLike;
  signOutError?: { message: string; status?: number; code?: string } | null;
  session?: { status: "present" | "absent" } | { error: { message: string } };
}): { client: AuthClientLike; calls: FakeCalls } {
  const calls: FakeCalls = { signUp: null, signIn: null, signOut: 0 };
  const sessionState = options.session ?? { status: "present" };

  const client: AuthClientLike = {
    auth: {
      async signUp(credentials) {
        calls.signUp = credentials;
        return options.signUp ?? authResult({});
      },
      async signInWithPassword(credentials) {
        calls.signIn = credentials;
        return (
          options.signIn ??
          authResult({ data: { user: USER, session: { user: USER } } })
        );
      },
      async signOut() {
        calls.signOut += 1;
        return { error: options.signOutError ?? null };
      },
      async getSession() {
        if ("error" in sessionState) {
          return { data: { session: null }, error: sessionState.error };
        }
        return {
          data: { session: sessionState.status === "present" ? { user: USER } : null },
          error: null,
        };
      },
    },
  };

  return { client, calls };
}

test("signup signs the user in when Supabase returns a session", async () => {
  const { client, calls } = fakeClient({});

  const result = await signUpWithEmail("person@example.com", "secret123", client);

  assert.deepEqual(result, { ok: true, status: "signed-in", userId: "user-1" });
  assert.deepEqual(calls.signUp, {
    email: "person@example.com",
    password: "secret123",
  });
});

test("signup reports pending confirmation instead of pretending to sign in", async () => {
  const { client } = fakeClient({
    signUp: authResult({ data: { user: USER, session: null } }),
  });

  const result = await signUpWithEmail("person@example.com", "secret123", client);

  assert.deepEqual(result, {
    ok: true,
    status: "confirmation-required",
    email: "person@example.com",
  });
});

test("signup failure returns a safe reason and never the provider message", async () => {
  const { client } = fakeClient({
    signUp: authResult({
      data: { user: null, session: null },
      error: {
        message: "internal: duplicate key on auth.users (person@example.com)",
        status: 422,
        code: "user_already_exists",
      },
    }),
  });

  const result = await signUpWithEmail("person@example.com", "secret123", client);

  assert.equal(result.ok, false);
  assert.deepEqual(result, {
    ok: false,
    reason: "already-registered",
    message: "An account with this email address already exists.",
  });
  assert.equal(JSON.stringify(result).includes("auth.users"), false);
});

test("signup with a weak password is classified from the provider code", async () => {
  const { client } = fakeClient({
    signUp: authResult({
      data: { user: null, session: null },
      error: { message: "Password should be at least 6 characters", status: 422, code: "weak_password" },
    }),
  });

  const result = await signUpWithEmail("person@example.com", "secret123", client);

  assert.deepEqual(result, {
    ok: false,
    reason: "rejected",
    message: "Choose a stronger password.",
  });
});

test("signup rejects unusable input before calling Supabase", async () => {
  const { client, calls } = fakeClient({});

  const badEmail = await signUpWithEmail("not-an-email", "secret123", client);
  const shortPassword = await signUpWithEmail("person@example.com", "short", client);

  assert.deepEqual(badEmail, {
    ok: false,
    reason: "invalid-input",
    message: "Enter a valid email address.",
  });
  assert.deepEqual(shortPassword, {
    ok: false,
    reason: "invalid-input",
    message: "Password must be at least 6 characters.",
  });
  assert.equal(calls.signUp, null);
});

test("login signs in and trims the email address", async () => {
  const { client, calls } = fakeClient({});

  const result = await signInWithEmail("  person@example.com ", "secret123", client);

  assert.deepEqual(result, { ok: true, status: "signed-in", userId: "user-1" });
  assert.deepEqual(calls.signIn, {
    email: "person@example.com",
    password: "secret123",
  });
});

test("login failure is reported as incorrect credentials without provider text", async () => {
  const { client } = fakeClient({
    signIn: authResult({
      data: { user: null, session: null },
      error: {
        message: "Invalid login credentials — user person@example.com not found",
        status: 400,
        code: "invalid_credentials",
      },
    }),
  });

  const result = await signInWithEmail("person@example.com", "wrong-password", client);

  assert.deepEqual(result, {
    ok: false,
    reason: "invalid-credentials",
    message: "Email or password is incorrect.",
  });
  assert.equal(JSON.stringify(result).includes("not found"), false);
});

test("login surfaces an unconfirmed email as its own state", async () => {
  const { client } = fakeClient({
    signIn: authResult({
      data: { user: null, session: null },
      error: { message: "Email not confirmed", status: 400, code: "email_not_confirmed" },
    }),
  });

  const result = await signInWithEmail("person@example.com", "secret123", client);

  assert.deepEqual(result, {
    ok: false,
    reason: "email-not-confirmed",
    message: "Confirm your email address before signing in.",
  });
});

test("login never reports success without a session", async () => {
  const { client } = fakeClient({
    signIn: authResult({ data: { user: USER, session: null } }),
  });

  const result = await signInWithEmail("person@example.com", "secret123", client);

  assert.deepEqual(result, {
    ok: false,
    reason: "unexpected",
    message: "An unexpected error occurred. Please try again.",
  });
});

test("a transport failure becomes an unexpected failure, not a crash", async () => {
  const client: AuthClientLike = {
    auth: {
      async signUp() {
        throw new TypeError("fetch failed for https://project.supabase.co");
      },
      async signInWithPassword() {
        throw new TypeError("fetch failed for https://project.supabase.co");
      },
      async signOut() {
        throw new TypeError("fetch failed");
      },
      async getSession() {
        throw new TypeError("fetch failed");
      },
    },
  };

  const result = await signInWithEmail("person@example.com", "secret123", client);

  assert.deepEqual(result, {
    ok: false,
    reason: "unexpected",
    message: "An unexpected error occurred. Please try again.",
  });
  assert.equal(JSON.stringify(result).includes("supabase.co"), false);
});

test("signout ends the session and reports failure safely", async () => {
  const { client, calls } = fakeClient({});

  const success = await signOut(client);
  assert.deepEqual(success, { ok: true });
  assert.equal(calls.signOut, 1);

  const { client: failing } = fakeClient({
    signOutError: { message: "Auth session missing!", status: 400 },
  });
  const failure = await signOut(failing);

  assert.deepEqual(failure, {
    ok: false,
    reason: "invalid-credentials",
    message: "Email or password is incorrect.",
  });
});

test("an authenticated session is detected from Supabase storage", async () => {
  const { client } = fakeClient({ session: { status: "present" } });

  const state = await getCurrentSession(client);

  assert.deepEqual(state, {
    status: "authenticated",
    userId: "user-1",
    email: "person@example.com",
  });
});

test("a missing session is reported as unauthenticated", async () => {
  const { client } = fakeClient({ session: { status: "absent" } });

  const state = await getCurrentSession(client);

  assert.deepEqual(state, { status: "unauthenticated" });
});

test("an unreadable session is distinct from being signed out", async () => {
  const { client } = fakeClient({
    session: { error: { message: "stale token in localStorage" } },
  });

  const state = await getCurrentSession(client);

  assert.deepEqual(state, {
    status: "error",
    message: "Your session could not be read. Try signing in again.",
  });
  assert.equal(JSON.stringify(state).includes("localStorage"), false);
});

test("an authenticated user without an email still yields a usable state", async () => {
  const client: AuthClientLike = {
    auth: {
      async signUp() {
        return authResult({});
      },
      async signInWithPassword() {
        return authResult({});
      },
      async signOut() {
        return { error: null };
      },
      async getSession() {
        return { data: { session: { user: { id: "user-2" } } }, error: null };
      },
    },
  };

  assert.deepEqual(await getCurrentSession(client), {
    status: "authenticated",
    userId: "user-2",
    email: null,
  });
});

test("without Supabase configuration every operation fails clearly", async () => {
  // No NEXT_PUBLIC_SUPABASE_* variables exist in this process, so the default
  // client is absent and nothing may fall back to fake credentials.
  const expectedFailure = {
    ok: false,
    reason: "unconfigured",
    message:
      "Authentication is not available: Supabase is not configured for this environment.",
  };

  assert.deepEqual(
    await signUpWithEmail("person@example.com", "secret123"),
    expectedFailure,
  );
  assert.deepEqual(
    await signInWithEmail("person@example.com", "secret123"),
    expectedFailure,
  );
  assert.deepEqual(await signOut(), expectedFailure);
  assert.deepEqual(await getCurrentSession(), { status: "unconfigured" });
});


