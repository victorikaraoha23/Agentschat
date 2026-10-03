/**
 * Unit tests for the shell access decision (Task 4.1).
 *
 * `toShellAccess` is a pure function of `SessionState`, so these tests need
 * no Supabase, no router, and no rendered component — just the mapping.
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { toShellAccess } from "./shell-access.ts";
import type { SessionState } from "./auth.ts";

test("a resolving session maps to the loading view", () => {
  assert.deepEqual(toShellAccess(null), { view: "loading" });
});

test("an authenticated session grants access with the caller's identity", () => {
  const session: SessionState = {
    status: "authenticated",
    userId: "user-1",
    email: "person@example.com",
  };
  assert.deepEqual(toShellAccess(session), {
    view: "granted",
    userId: "user-1",
    email: "person@example.com",
  });
});

test("an authenticated session without an email still grants access", () => {
  const session: SessionState = {
    status: "authenticated",
    userId: "user-1",
    email: null,
  };
  assert.deepEqual(toShellAccess(session), {
    view: "granted",
    userId: "user-1",
    email: null,
  });
});

test("an unauthenticated session is denied as unauthenticated", () => {
  const session: SessionState = { status: "unauthenticated" };
  assert.deepEqual(toShellAccess(session), {
    view: "denied",
    reason: "unauthenticated",
  });
});

test("an unconfigured backend is denied without claiming a sign-in state", () => {
  const session: SessionState = { status: "unconfigured" };
  assert.deepEqual(toShellAccess(session), {
    view: "denied",
    reason: "unconfigured",
  });
});

test("an unreadable session is denied as unreadable, never granted", () => {
  const session: SessionState = {
    status: "error",
    message: "Your session could not be read: sign in again.",
  };
  assert.deepEqual(toShellAccess(session), {
    view: "denied",
    reason: "unreadable",
  });
});
