/**
 * Unit tests for the conversation thread state (Task 6.2).
 *
 * Every transition is a pure function of the state and the API's answer, so
 * these tests cover what the page may show after an attempt — a stored message,
 * a failure, or a refused second submit — with no browser and no request.
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  beginMessageSubmit,
  initialThreadState,
  messageSubmitted,
  messageSubmitFailed,
  type ConversationThreadState,
} from "./conversation-thread.ts";
import type { Message } from "./messages-api.ts";

function message(overrides: Partial<Message> = {}): Message {
  return {
    id: "323e4567-e89b-12d3-a456-426614174000",
    conversationId: "223e4567-e89b-12d3-a456-426614174000",
    userId: "123e4567-e89b-12d3-a456-426614174000",
    role: "user",
    content: "Hello",
    createdAt: "2026-10-04T12:00:00Z",
    ...overrides,
  };
}

test("an opened conversation has no messages and no pending submit", () => {
  assert.deepEqual(initialThreadState(), { messages: [], submitting: false, error: null });
});

test("starting a submit marks it in flight and clears an earlier error", () => {
  const failed = messageSubmitFailed(initialThreadState(), "Request failed.");

  assert.deepEqual(beginMessageSubmit(failed), {
    messages: [],
    submitting: true,
    error: null,
  });
});

test("a second submit cannot start while one is in flight", () => {
  const inFlight = beginMessageSubmit(initialThreadState());

  assert.equal(beginMessageSubmit(inFlight), inFlight);
});

test("a confirmed message is appended and the submit ends", () => {
  const inFlight = beginMessageSubmit(initialThreadState());

  const state = messageSubmitted(inFlight, message());

  assert.equal(state.messages.length, 1);
  assert.deepEqual(state.messages[0], message());
  assert.equal(state.submitting, false);
  assert.equal(state.error, null);
});

test("messages stay in the order they were confirmed", () => {
  const first = messageSubmitted(beginMessageSubmit(initialThreadState()), message());
  const second = messageSubmitted(beginMessageSubmit(first), message({ id: "second", content: "Second" }));

  assert.deepEqual(
    second.messages.map((entry) => entry.content),
    ["Hello", "Second"],
  );
});

test("a confirmed message clears a previous failure", () => {
  const failed = messageSubmitFailed(initialThreadState(), "Request failed.");

  const state = messageSubmitted(failed, message());

  assert.equal(state.error, null);
  assert.equal(state.messages.length, 1);
});

test("a failed submit adds nothing to the conversation", () => {
  const inFlight: ConversationThreadState = {
    messages: [message()],
    submitting: true,
    error: null,
  };

  const state = messageSubmitFailed(inFlight, "Request failed.");

  assert.deepEqual(state, {
    messages: [message()],
    submitting: false,
    error: "Request failed.",
  });
});

test("a retry after a failure is allowed again", () => {
  const failed = messageSubmitFailed(initialThreadState(), "Request failed.");

  assert.equal(beginMessageSubmit(failed).submitting, true);
});
