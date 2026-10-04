/**
 * Unit tests for the message API boundary (Task 6.2).
 *
 * `createMessage` never throws and never reaches the network: the tests inject
 * a `fetch` and assert the request it builds (path, method, bearer token, body)
 * and the typed result every failure category produces.
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  createMessage,
  MESSAGE_CONTENT_MAX_LENGTH,
  messageContentProblem,
  type Message,
  type MessageResult,
} from "./messages-api.ts";

const CONVERSATION_ID = "223e4567-e89b-12d3-a456-426614174000";
const TOKEN = "header.payload.signature";

const MESSAGE_PAYLOAD = {
  id: "323e4567-e89b-12d3-a456-426614174000",
  conversation_id: CONVERSATION_ID,
  user_id: "123e4567-e89b-12d3-a456-426614174000",
  role: "user",
  content: "Hello",
  created_at: "2026-10-04T12:00:00Z",
};

interface Recorded {
  url: string;
  init: RequestInit | undefined;
}

/** A `fetch` that records the request and answers with the prepared response. */
function recordingFetch(response: Response | Error): {
  fetchImpl: (url: string, init?: RequestInit) => Promise<Response>;
  calls: Recorded[];
} {
  const calls: Recorded[] = [];
  return {
    calls,
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      if (response instanceof Error) {
        throw response;
      }
      return response;
    },
  };
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

async function send(
  fetchImpl: (url: string, init?: RequestInit) => Promise<Response>,
  content = "Hello",
): Promise<MessageResult> {
  return createMessage({
    conversationId: CONVERSATION_ID,
    content,
    accessToken: TOKEN,
    fetchImpl,
  });
}

test("a sent message posts the content to the conversation's messages path", async () => {
  const { fetchImpl, calls } = recordingFetch(jsonResponse(201, MESSAGE_PAYLOAD));

  await send(fetchImpl);

  assert.equal(calls.length, 1);
  assert.ok(calls[0].url.endsWith(`/conversations/${CONVERSATION_ID}/messages`));
  assert.equal(calls[0].init?.method, "POST");
  assert.deepEqual(JSON.parse(String(calls[0].init?.body)), { content: "Hello" });
});

test("the request carries the session token and never a user id", async () => {
  const { fetchImpl, calls } = recordingFetch(jsonResponse(201, MESSAGE_PAYLOAD));

  await send(fetchImpl);

  const headers = calls[0].init?.headers as Record<string, string>;
  assert.equal(headers.Authorization, `Bearer ${TOKEN}`);
  assert.equal(String(calls[0].init?.body).includes("user_id"), false);
  assert.equal(calls[0].url.includes("user_id"), false);
});

test("a created message is returned as the typed domain message", async () => {
  const { fetchImpl } = recordingFetch(jsonResponse(201, MESSAGE_PAYLOAD));

  const result = await send(fetchImpl);

  assert.equal(result.ok, true);
  const message: Message = result.ok ? result.message : ({} as Message);
  assert.deepEqual(message, {
    id: "323e4567-e89b-12d3-a456-426614174000",
    conversationId: CONVERSATION_ID,
    userId: "123e4567-e89b-12d3-a456-426614174000",
    role: "user",
    content: "Hello",
    createdAt: "2026-10-04T12:00:00Z",
  });
});

test("without a usable session the request is never sent", async () => {
  const { fetchImpl, calls } = recordingFetch(jsonResponse(201, MESSAGE_PAYLOAD));

  const result = await createMessage({
    conversationId: CONVERSATION_ID,
    content: "Hello",
    accessToken: null,
    fetchImpl,
  });

  assert.deepEqual(result, {
    ok: false,
    reason: "unauthenticated",
    message: "Your message could not be sent: sign in again.",
  });
  assert.equal(calls.length, 0);
});

test("a rejected token is an unauthenticated failure", async () => {
  for (const status of [401, 403]) {
    const { fetchImpl } = recordingFetch(jsonResponse(status, { detail: "nope" }));

    const result = await send(fetchImpl);

    assert.equal(result.ok, false);
    assert.equal(result.ok === false && result.reason, "unauthenticated");
    assert.equal(result.ok === false && result.statusCode, status);
  }
});

test("a conversation the caller cannot use is not-found, never a 403", async () => {
  const { fetchImpl } = recordingFetch(
    jsonResponse(404, { detail: "Conversation not found." }),
  );

  const result = await send(fetchImpl);

  assert.deepEqual(result, {
    ok: false,
    reason: "not-found",
    message: "That conversation could not be found.",
    statusCode: 404,
  });
});

test("rejected content is invalid-input with a fixed message", async () => {
  const { fetchImpl } = recordingFetch(jsonResponse(422, { detail: [{ msg: "raw" }] }));

  const result = await send(fetchImpl);

  assert.equal(result.ok, false);
  assert.equal(result.ok === false && result.reason, "invalid-input");
  assert.equal(
    result.ok === false && result.message,
    "Your message could not be sent: check its content.",
  );
});

test("a server failure reports the status code only", async () => {
  const { fetchImpl } = recordingFetch(jsonResponse(500, { detail: "traceback" }));

  const result = await send(fetchImpl);

  assert.deepEqual(result, {
    ok: false,
    reason: "http",
    message: "The API responded with HTTP 500.",
    statusCode: 500,
  });
});

test("a network failure is reported without throwing", async () => {
  const { fetchImpl } = recordingFetch(new Error("socket closed"));

  const result = await send(fetchImpl);

  assert.deepEqual(result, { ok: false, reason: "network", message: "Request failed." });
});

test("a response that is not JSON is an invalid-response failure", async () => {
  const { fetchImpl } = recordingFetch(new Response("<html>", { status: 201 }));

  const result = await send(fetchImpl);

  assert.deepEqual(result, {
    ok: false,
    reason: "invalid-response",
    message: "The API response was not valid JSON.",
  });
});

test("a body without the message fields is an invalid-response failure", async () => {
  const { fetchImpl } = recordingFetch(jsonResponse(201, { id: "only-an-id" }));

  const result = await send(fetchImpl);

  assert.deepEqual(result, {
    ok: false,
    reason: "invalid-response",
    message: "The API response did not contain a message.",
  });
});

test("a blank draft is reported as a problem instead of being sent", () => {
  assert.equal(messageContentProblem(""), "Type a message first.");
  assert.equal(messageContentProblem("   \n "), "Type a message first.");
});

test("an overlong draft is reported before a round trip", () => {
  assert.notEqual(
    messageContentProblem("x".repeat(MESSAGE_CONTENT_MAX_LENGTH + 1)),
    null,
  );
  assert.equal(messageContentProblem("x".repeat(MESSAGE_CONTENT_MAX_LENGTH)), null);
});

test("a normal draft has no problem to report", () => {
  assert.equal(messageContentProblem("Hello"), null);
});
