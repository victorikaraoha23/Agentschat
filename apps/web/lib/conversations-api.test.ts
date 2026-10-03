/**
 * Unit tests for the conversation-creation boundary (Task 5.2).
 *
 * `fetch` and the access token are injected, so no test touches the network
 * or Supabase. Only the bearer token and the optional title are ever sent —
 * never a user id.
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { createConversation } from "./conversations-api.ts";

const TOKEN = "session-access-token";

const CONVERSATION_BODY = {
  id: "223e4567-e89b-12d3-a456-426614174000",
  user_id: "123e4567-e89b-12d3-a456-426614174000",
  title: null,
  created_at: "2026-10-04T12:00:00Z",
  updated_at: "2026-10-04T12:00:00Z",
};

function jsonResponse(body: unknown, status = 201): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

test("posts to /conversations and returns the created conversation", async () => {
  let requestedUrl: string | undefined;
  let method: string | undefined;
  let authorization: string | undefined;
  let sentBody: unknown;
  const result = await createConversation({
    title: "hello",
    accessToken: TOKEN,
    fetchImpl: async (url, init) => {
      requestedUrl = url;
      method = init?.method;
      authorization = new Headers(init?.headers).get("Authorization") ?? undefined;
      sentBody = JSON.parse(String(init?.body));
      return jsonResponse({ ...CONVERSATION_BODY, title: "hello" });
    },
  });

  assert.match(requestedUrl ?? "", /\/conversations$/);
  assert.equal(method, "POST");
  assert.equal(authorization, `Bearer ${TOKEN}`);
  assert.deepEqual(sentBody, { title: "hello" });
  assert.equal(result.ok, true);
  assert.deepEqual(result.ok ? result.conversation : null, {
    id: CONVERSATION_BODY.id,
    userId: CONVERSATION_BODY.user_id,
    title: "hello",
    createdAt: CONVERSATION_BODY.created_at,
    updatedAt: CONVERSATION_BODY.updated_at,
  });
});

test("omitting the title sends an empty object, not a user id", async () => {
  let sentBody: unknown;
  const result = await createConversation({
    accessToken: TOKEN,
    fetchImpl: async (_url, init) => {
      sentBody = JSON.parse(String(init?.body));
      return jsonResponse(CONVERSATION_BODY);
    },
  });

  assert.deepEqual(sentBody, {});
  assert.equal(result.ok, true);
});

test("an unauthenticated request is reported without fetching anything", async () => {
  let called = false;
  const result = await createConversation({
    title: "hello",
    accessToken: null,
    fetchImpl: async () => {
      called = true;
      return jsonResponse(CONVERSATION_BODY);
    },
  });

  assert.equal(called, false);
  assert.deepEqual(result, {
    ok: false,
    reason: "unauthenticated",
    message: "Your conversation could not be created: sign in again.",
  });
});

test("a rejected session is reported as unauthenticated, not as a generic failure", async () => {
  const result = await createConversation({
    accessToken: TOKEN,
    fetchImpl: async () => jsonResponse({ detail: "Authentication required." }, 401),
  });

  assert.deepEqual(result, {
    ok: false,
    reason: "unauthenticated",
    message: "Your conversation could not be created: your session is not valid.",
    statusCode: 401,
  });
  assert.equal(JSON.stringify(result).includes("Authentication required."), false);
});

test("a 422 becomes invalid-input with a fixed message", async () => {
  const result = await createConversation({
    title: "x".repeat(201),
    accessToken: TOKEN,
    fetchImpl: async () =>
      jsonResponse({ detail: "String should have at most 200 characters" }, 422),
  });

  assert.deepEqual(result, {
    ok: false,
    reason: "invalid-input",
    message: "Give the conversation a title of 200 characters or fewer.",
    statusCode: 422,
  });
  assert.equal(JSON.stringify(result).includes("String should"), false);
});

test("a server error reports the status code and never the body", async () => {
  const result = await createConversation({
    accessToken: TOKEN,
    fetchImpl: async () =>
      jsonResponse({ detail: "The conversation could not be created." }, 503),
  });

  assert.deepEqual(result, {
    ok: false,
    reason: "http",
    message: "The API responded with HTTP 503.",
    statusCode: 503,
  });
  assert.equal(JSON.stringify(result).includes("could not be created"), false);
});

test("a malformed body is rejected as an invalid response", async () => {
  const wrongShape = await createConversation({
    accessToken: TOKEN,
    fetchImpl: async () => jsonResponse({ id: CONVERSATION_BODY.id }),
  });

  assert.deepEqual(wrongShape, {
    ok: false,
    reason: "invalid-response",
    message: "The API response did not contain a conversation.",
  });
});
