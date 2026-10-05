/**
 * Unit tests for the conversation thread state (Tasks 6.2 and 8.3).
 *
 * Every transition is a pure function of the state and the API's answer, so
 * these tests cover what the page may show after an attempt -- a stored reply,
 * a failure, a refused second submit, and a reply arriving in pieces -- with no
 * browser and no request.
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  beginMessageSubmit,
  initialThreadState,
  streamCompleted,
  streamDelta,
  streamFailed,
} from "./conversation-thread.ts";
import type { Message } from "./messages-api.ts";

function message(overrides: Partial<Message> = {}): Message {
  return {
    id: "323e4567-e89b-12d3-a456-426614174000",
    conversationId: "223e4567-e89b-12d3-a456-426614174000",
    userId: "123e4567-e89b-12d3-a456-426614174000",
    role: "assistant",
    content: "Hello there",
    createdAt: "2026-10-04T12:00:00Z",
    ...overrides,
  };
}

test("an opened conversation has no messages, no pending submit, and no reply", () => {
  assert.deepEqual(initialThreadState(), {
    messages: [],
    submitting: false,
    error: null,
    streamStatus: "idle",
    streamingContent: "",
  });
});

test("starting a send marks it in flight and clears an earlier error", () => {
  const failed = streamFailed(initialThreadState(), "Request failed.");

  assert.deepEqual(beginMessageSubmit(failed), {
    messages: [],
    submitting: true,
    error: null,
    streamStatus: "streaming",
    streamingContent: "",
  });
});

test("a second send cannot start while one is in flight", () => {
  const inFlight = beginMessageSubmit(initialThreadState());

  assert.equal(beginMessageSubmit(inFlight), inFlight);
});

test("deltas accumulate in the order they arrived", () => {
  let state = beginMessageSubmit(initialThreadState());
  state = streamDelta(state, "fake ");
  state = streamDelta(state, "assistant reply");

  assert.equal(state.streamingContent, "fake assistant reply");
});

test("a streaming reply is not yet a message in the conversation", () => {
  const state = streamDelta(beginMessageSubmit(initialThreadState()), "half");

  assert.equal(state.streamingContent, "half");
  assert.deepEqual(state.messages, []);
});

test("completion appends the stored reply and ends the send", () => {
  let state = streamDelta(beginMessageSubmit(initialThreadState()), "Hello there");

  state = streamCompleted(state, message());

  assert.equal(state.messages.length, 1);
  assert.deepEqual(state.messages[0], message());
  assert.equal(state.submitting, false);
  assert.equal(state.streamStatus, "completed");
});

test("completion clears the provisional text now the reply has a home", () => {
  let state = streamDelta(beginMessageSubmit(initialThreadState()), "Hello there");

  state = streamCompleted(state, message());

  assert.equal(state.streamingContent, "");
});

test("a failed stream adds nothing and discards the partial reply", () => {
  let state = streamDelta(beginMessageSubmit(initialThreadState()), "Hello, I can hel");
  state = streamCompleted(state, message());

  const failed = streamFailed(state, "The agent run failed.");

  assert.equal(failed.streamingContent, "");
  assert.equal(failed.streamStatus, "error");
  assert.equal(failed.error, "The agent run failed.");
  // The messages confirmed earlier are untouched by the failure.
  assert.equal(failed.messages.length, 1);
});

test("a failed stream leaves the composer usable", () => {
  const failed = streamFailed(beginMessageSubmit(initialThreadState()), "It failed.");

  assert.equal(failed.submitting, false);
});

test("a retry after a failure is allowed again", () => {
  const failed = streamFailed(initialThreadState(), "Request failed.");

  assert.equal(beginMessageSubmit(failed).submitting, true);
});

test("messages stay in the order they were confirmed", () => {
  let state = streamCompleted(beginMessageSubmit(initialThreadState()), message());
  state = streamCompleted(
    beginMessageSubmit(state),
    message({ id: "second", content: "Second" }),
  );

  assert.deepEqual(
    state.messages.map((entry) => entry.content),
    ["Hello there", "Second"],
  );
});
