/**
 * Unit tests for the profile request boundary (Task 3.3).
 *
 * `fetch` and the access token are injected, so no test touches the network or
 * Supabase. `node --test` isolates each file in its own process, so no
 * NEXT_PUBLIC_* variable is set here.
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { fetchMyProfile, type ProfileResult } from "./profile-api.ts";

const TOKEN = "session-access-token";

const PROFILE_BODY = {
  user_id: "123e4567-e89b-12d3-a456-426614174000",
  created_at: "2026-10-01T12:00:00Z",
  updated_at: "2026-10-02T12:00:00Z",
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

test("requests /me with the bearer token and returns the profile", async () => {
  let requestedUrl: string | undefined;
  let authorization: string | undefined;
  const result = await fetchMyProfile({
    accessToken: TOKEN,
    fetchImpl: async (url, init) => {
      requestedUrl = url;
      authorization = new Headers(init?.headers).get("Authorization") ?? undefined;
      return jsonResponse(PROFILE_BODY);
    },
  });

  assert.match(requestedUrl ?? "", /\/me$/);
  assert.equal(authorization, `Bearer ${TOKEN}`);
  assert.deepEqual(result, {
    ok: true,
    profile: {
      userId: PROFILE_BODY.user_id,
      createdAt: PROFILE_BODY.created_at,
      updatedAt: PROFILE_BODY.updated_at,
    },
  });
});

test("sends no user id of its own — identity comes from the token", async () => {
  let requestedUrl: string | undefined;
  let sentBody: BodyInit | null | undefined;
  await fetchMyProfile({
    accessToken: TOKEN,
    fetchImpl: async (url, init) => {
      requestedUrl = url;
      sentBody = init?.body;
      return jsonResponse(PROFILE_BODY);
    },
  });

  assert.equal(sentBody ?? null, null);
  assert.equal((requestedUrl ?? "").includes(PROFILE_BODY.user_id), false);
});

test("an unauthenticated request is reported without fetching anything", async () => {
  let called = false;
  const result = await fetchMyProfile({
    accessToken: null,
    fetchImpl: async () => {
      called = true;
      return jsonResponse(PROFILE_BODY);
    },
  });

  assert.equal(called, false);
  assert.deepEqual(result, {
    ok: false,
    reason: "unauthenticated",
    message: "Your profile could not be loaded: sign in again.",
  });
});

test("a rejected session is reported as unauthenticated, not as a generic failure", async () => {
  const result = await fetchMyProfile({
    accessToken: TOKEN,
    fetchImpl: async () => jsonResponse({ detail: "Authentication required." }, 401),
  });

  assert.deepEqual(result, {
    ok: false,
    reason: "unauthenticated",
    message: "Your profile could not be loaded: your session is not valid.",
    statusCode: 401,
  });
  assert.equal(JSON.stringify(result).includes("Authentication required."), false);
});

test("a server error reports the status code and never the body", async () => {
  const result = await fetchMyProfile({
    accessToken: TOKEN,
    fetchImpl: async () =>
      jsonResponse({ detail: "The authenticated profile is unavailable." }, 500),
  });

  assert.deepEqual(result, {
    ok: false,
    reason: "http",
    message: "The API responded with HTTP 500.",
    statusCode: 500,
  });
  assert.equal(JSON.stringify(result).includes("unavailable"), false);
});

test("a network failure is classified without leaking the error", async () => {
  const result = await fetchMyProfile({
    accessToken: TOKEN,
    fetchImpl: async () => {
      throw new TypeError("fetch failed for http://127.0.0.1:8000/me");
    },
  });

  assert.deepEqual(result, {
    ok: false,
    reason: "network",
    message: "Request failed.",
  });
  assert.equal(JSON.stringify(result).includes("127.0.0.1"), false);
});

test("a malformed body is rejected as an invalid response", async () => {
  const notJson = await fetchMyProfile({
    accessToken: TOKEN,
    fetchImpl: async () => new Response("<html>oops</html>", { status: 200 }),
  });
  const wrongShape = await fetchMyProfile({
    accessToken: TOKEN,
    fetchImpl: async () => jsonResponse({ user_id: PROFILE_BODY.user_id }),
  });

  assert.deepEqual(notJson, {
    ok: false,
    reason: "invalid-response",
    message: "The API response was not valid JSON.",
  });
  assert.deepEqual(wrongShape, {
    ok: false,
    reason: "invalid-response",
    message: "The API response did not contain a profile.",
  });
});

test("an unreadable session is reported without a token being available", async () => {
  // No NEXT_PUBLIC_SUPABASE_* configuration exists in this process, so the
  // session cannot be read and no request may be attempted with a fake token.
  let called = false;
  const result: ProfileResult = await fetchMyProfile({
    fetchImpl: async () => {
      called = true;
      return jsonResponse(PROFILE_BODY);
    },
  });

  assert.equal(called, false);
  assert.equal(result.ok, false);
  assert.equal(result.ok ? null : result.reason, "unauthenticated");
});
