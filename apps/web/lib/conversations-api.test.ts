/**
 * Unit tests for the conversation boundary (Tasks 5.2–5.3).
 *
 * `fetch` and the access token are injected, so no test touches the network
 * or Supabase. Every request carries only the bearer token — never a user id —
 * whether it creates a conversation, lists them, or reads one.
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { createConversation, getConversation, listConversations } from "./conversations-api.ts";

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

test("list reads /conversations with only the bearer token and keeps the API order", async () => {
  let requestedUrl: string | undefined;
  let method: string | undefined;
  let authorization: string | undefined;
  let sentBody: unknown;
  const newest = {
    ...CONVERSATION_BODY,
    id: "323e4567-e89b-12d3-a456-426614174000",
    title: "newest",
    updated_at: "2026-10-04T13:00:00Z",
  };
  const result = await listConversations({
    accessToken: TOKEN,
    fetchImpl: async (url, init) => {
      requestedUrl = url;
      method = init?.method;
      authorization = new Headers(init?.headers).get("Authorization") ?? undefined;
      sentBody = init?.body;
      return jsonResponse({ items: [newest, CONVERSATION_BODY] }, 200);
    },
  });

  assert.match(requestedUrl ?? "", /\/conversations$/);
  assert.equal(method, undefined);
  assert.equal(authorization, `Bearer ${TOKEN}`);
  assert.equal(sentBody, undefined);
  assert.equal(result.ok, true);
  const conversations = result.ok ? result.conversations : [];
  assert.deepEqual(
    conversations.map((conversation) => conversation.id),
    [newest.id, CONVERSATION_BODY.id],
  );
  assert.equal(conversations[0]?.title, "newest");
});

test("an empty list is a success with no conversations, not an error", async () => {
  const result = await listConversations({
    accessToken: TOKEN,
    fetchImpl: async () => jsonResponse({ items: [] }, 200),
  });

  assert.deepEqual(result, { ok: true, conversations: [] });
});

test("listing without a session is reported without fetching anything", async () => {
  let called = false;
  const result = await listConversations({
    accessToken: null,
    fetchImpl: async () => {
      called = true;
      return jsonResponse({ items: [] }, 200);
    },
  });

  assert.equal(called, false);
  assert.deepEqual(result, {
    ok: false,
    reason: "unauthenticated",
    message: "Your conversations could not be loaded: sign in again.",
  });
});

test("a rejected session while listing is unauthenticated, not a generic failure", async () => {
  const result = await listConversations({
    accessToken: TOKEN,
    fetchImpl: async () => jsonResponse({ detail: "Authentication required." }, 401),
  });

  assert.deepEqual(result, {
    ok: false,
    reason: "unauthenticated",
    message: "Your conversations could not be loaded: your session is not valid.",
    statusCode: 401,
  });
  assert.equal(JSON.stringify(result).includes("Authentication required."), false);
});

test("a server error while listing reports the status and never the body", async () => {
  const result = await listConversations({
    accessToken: TOKEN,
    fetchImpl: async () =>
      jsonResponse({ detail: "The conversations could not be read." }, 503),
  });

  assert.deepEqual(result, {
    ok: false,
    reason: "http",
    message: "The API responded with HTTP 503.",
    statusCode: 503,
  });
  assert.equal(JSON.stringify(result).includes("could not be read"), false);
});

test("a network failure while listing is a network result", async () => {
  const result = await listConversations({
    accessToken: TOKEN,
    fetchImpl: async () => {
      throw new TypeError("fetch failed");
    },
  });

  assert.deepEqual(result, { ok: false, reason: "network", message: "Request failed." });
});

test("a list that is not the contracted shape is an invalid response", async () => {
  const wrongShape = await listConversations({
    accessToken: TOKEN,
    fetchImpl: async () => jsonResponse({ conversations: [] }, 200),
  });

  assert.deepEqual(wrongShape, {
    ok: false,
    reason: "invalid-response",
    message: "The API response did not contain a conversation list.",
  });

  const wrongItems = await listConversations({
    accessToken: TOKEN,
    fetchImpl: async () => jsonResponse({ items: [{ id: "not-a-conversation" }] }, 200),
  });
  assert.equal(wrongItems.ok, false);
  assert.equal(wrongItems.ok ? null : wrongItems.reason, "invalid-response");
});

test("a non-JSON list response is an invalid response, never raw text", async () => {
  const notJson = await listConversations({
    accessToken: TOKEN,
    fetchImpl: async () => new Response("<html>gateway</html>", { status: 200 }),
  });

  assert.deepEqual(notJson, {
    ok: false,
    reason: "invalid-response",
    message: "The API response was not valid JSON.",
  });
  assert.equal(JSON.stringify(notJson).includes("gateway"), false);
});

test("reads the conversation by id with only the bearer token", async () => {
  let requestedUrl: string | undefined;
  let method: string | undefined;
  let authorization: string | undefined;
  let sentBody: unknown;
  const result = await getConversation({
    conversationId: CONVERSATION_BODY.id,
    accessToken: TOKEN,
    fetchImpl: async (url, init) => {
      requestedUrl = url;
      method = init?.method;
      authorization = new Headers(init?.headers).get("Authorization") ?? undefined;
      sentBody = init?.body;
      return jsonResponse(CONVERSATION_BODY, 200);
    },
  });

  assert.ok(requestedUrl?.endsWith(`/conversations/${CONVERSATION_BODY.id}`));
  assert.equal(method, undefined);
  assert.equal(authorization, `Bearer ${TOKEN}`);
  assert.equal(sentBody, undefined);
  assert.equal(result.ok, true);
  assert.deepEqual(result.ok ? result.conversation : null, {
    id: CONVERSATION_BODY.id,
    userId: CONVERSATION_BODY.user_id,
    title: CONVERSATION_BODY.title,
    createdAt: CONVERSATION_BODY.created_at,
    updatedAt: CONVERSATION_BODY.updated_at,
  });
});

test("reading without a session is reported without fetching anything", async () => {
  let called = false;
  const result = await getConversation({
    conversationId: CONVERSATION_BODY.id,
    accessToken: null,
    fetchImpl: async () => {
      called = true;
      return jsonResponse(CONVERSATION_BODY, 200);
    },
  });

  assert.equal(called, false);
  assert.deepEqual(result, {
    ok: false,
    reason: "unauthenticated",
    message: "Your conversation could not be loaded: sign in again.",
  });
});

test("a rejected session while reading is unauthenticated, not a generic failure", async () => {
  const result = await getConversation({
    conversationId: CONVERSATION_BODY.id,
    accessToken: TOKEN,
    fetchImpl: async () => jsonResponse({ detail: "Authentication required." }, 401),
  });

  assert.deepEqual(result, {
    ok: false,
    reason: "unauthenticated",
    message: "Your conversation could not be loaded: your session is not valid.",
    statusCode: 401,
  });
  assert.equal(JSON.stringify(result).includes("Authentication required."), false);
});

test("a 404 read is not-found with a fixed message that leaks nothing", async () => {
  const missing = await getConversation({
    conversationId: CONVERSATION_BODY.id,
    accessToken: TOKEN,
    fetchImpl: async () => jsonResponse({ detail: "Conversation not found." }, 404),
  });

  assert.deepEqual(missing, {
    ok: false,
    reason: "not-found",
    message: "That conversation could not be found.",
    statusCode: 404,
  });
  // The API answers 404 for a missing conversation and for one owned by
  // someone else; this result must reveal neither the server's wording nor the
  // requested id.
  assert.equal(JSON.stringify(missing).includes("Conversation not found"), false);
  assert.equal(JSON.stringify(missing).includes(CONVERSATION_BODY.id), false);
});

test("a malformed id is invalid-input with a fixed message", async () => {
  const result = await getConversation({
    conversationId: "not-a-uuid",
    accessToken: TOKEN,
    fetchImpl: async () => jsonResponse({ detail: "Input should be a valid UUID" }, 422),
  });

  assert.deepEqual(result, {
    ok: false,
    reason: "invalid-input",
    message: "That conversation id is not valid.",
    statusCode: 422,
  });
  assert.equal(JSON.stringify(result).includes("valid UUID"), false);
});

test("a server error while reading reports the status and never the body", async () => {
  const result = await getConversation({
    conversationId: CONVERSATION_BODY.id,
    accessToken: TOKEN,
    fetchImpl: async () =>
      jsonResponse({ detail: "The conversation could not be read." }, 503),
  });

  assert.deepEqual(result, {
    ok: false,
    reason: "http",
    message: "The API responded with HTTP 503.",
    statusCode: 503,
  });
  assert.equal(JSON.stringify(result).includes("could not be read"), false);
});

test("a network failure while reading is a network result", async () => {
  const result = await getConversation({
    conversationId: CONVERSATION_BODY.id,
    accessToken: TOKEN,
    fetchImpl: async () => {
      throw new TypeError("fetch failed");
    },
  });

  assert.deepEqual(result, { ok: false, reason: "network", message: "Request failed." });
});

test("a response that is not a conversation is an invalid response", async () => {
  const wrongShape = await getConversation({
    conversationId: CONVERSATION_BODY.id,
    accessToken: TOKEN,
    fetchImpl: async () =>
      jsonResponse({ id: CONVERSATION_BODY.id, user_id: "x" }, 200),
  });

  assert.deepEqual(wrongShape, {
    ok: false,
    reason: "invalid-response",
    message: "The API response did not contain a conversation.",
  });
});

