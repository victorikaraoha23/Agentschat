/**
 * Tests for the streamed-execution reader (Task 8.3).
 *
 * The parser's whole job is to survive however the network splits the response,
 * so most of these feed the same body in deliberately awkward pieces. The stream
 * function is driven with a fake `fetch` returning a real `ReadableStream`, so the
 * reading loop, the accumulation, and the failure paths are exercised without a
 * browser or an API.
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  ExecutionEventParser,
  streamExecution,
  type ExecutionStreamEvent,
} from "./execution-stream.ts";

const CONVERSATION_ID = "223e4567-e89b-12d3-a456-426614174000";
const TOKEN = "header.payload.signature";

function frame(event: string, data: Record<string, unknown>): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

/** Build a Response whose body yields the given chunks in order. */
function streamResponse(chunks: string[], init?: { ok?: boolean; status?: number }) {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
  return new Response(body, {
    status: init?.status ?? 200,
    headers: { "content-type": "text/event-stream" },
  });
}

// --- Parser ------------------------------------------------------------------


test("a delta frame becomes a typed delta event", () => {
  const parser = new ExecutionEventParser();
  assert.deepEqual(parser.push(frame("delta", { content: "Hello" })), [
    { kind: "delta", content: "Hello" },
  ]);
});

test("a complete frame carries the message id", () => {
  const parser = new ExecutionEventParser();
  assert.deepEqual(parser.push(frame("complete", { message_id: "abc" })), [
    { kind: "complete", messageId: "abc" },
  ]);
});

test("an error frame carries the code and message", () => {
  const parser = new ExecutionEventParser();
  assert.deepEqual(parser.push(frame("error", { code: "failed", message: "It failed." })), [
    { kind: "error", code: "failed", message: "It failed." },
  ]);
});

test("an event split across chunks is read once it is complete", () => {
  const parser = new ExecutionEventParser();
  const whole = frame("delta", { content: "Hello" });

  assert.deepEqual(parser.push(whole.slice(0, 10)), []);
  assert.deepEqual(parser.push(whole.slice(10, whole.length - 4)), []);
  assert.deepEqual(parser.push(whole.slice(whole.length - 4)), [
    { kind: "delta", content: "Hello" },
  ]);
});

test("two events arriving in one chunk both arrive", () => {
  const parser = new ExecutionEventParser();
  const both = frame("delta", { content: "a" }) + frame("delta", { content: "b" });

  assert.deepEqual(parser.push(both), [
    { kind: "delta", content: "a" },
    { kind: "delta", content: "b" },
  ]);
});

test("one event split mid-JSON is not guessed at", () => {
  const parser = new ExecutionEventParser();
  const whole = frame("delta", { content: "Hello" });

  assert.deepEqual(parser.push(whole.slice(0, whole.indexOf("{") + 5)), []);
  assert.equal(parser.push(whole.slice(whole.indexOf("{") + 5)).length, 1);
});

test("an event split between its event and data lines still reads", () => {
  const parser = new ExecutionEventParser();
  assert.deepEqual(parser.push("event: delta\n"), []);
  assert.deepEqual(parser.push('data: {"content":"x"}\n\n'), [
    { kind: "delta", content: "x" },
  ]);
});

test("an unknown event name is ignored", () => {
  const parser = new ExecutionEventParser();
  assert.deepEqual(parser.push(frame("tool_use", { name: "search" })), []);
});

test("an unreadable payload is ignored rather than shown", () => {
  const parser = new ExecutionEventParser();
  assert.deepEqual(parser.push("event: delta\ndata: {not json\n\n"), []);
});

test("a keep-alive comment does not produce an event", () => {
  const parser = new ExecutionEventParser();
  assert.deepEqual(parser.push(": keep-alive\n\n"), []);
});

test("a delta with no content is ignored", () => {
  const parser = new ExecutionEventParser();
  assert.deepEqual(parser.push(frame("delta", {})), []);

// --- Consuming a stream ------------------------------------------------------


async function run(
  chunks: string[],
  init?: { ok?: boolean; status?: number },
): Promise<{ result: Awaited<ReturnType<typeof streamExecution>>; events: ExecutionStreamEvent[] }> {
  const events: ExecutionStreamEvent[] = [];
  const result = await streamExecution({
    conversationId: CONVERSATION_ID,
    content: "Hello",
    accessToken: TOKEN,
    onEvent: (event) => events.push(event),
    fetchImpl: async () => streamResponse(chunks, init),
  });
  return { result, events };
}

test("deltas are reported in order and the content is accumulated", async () => {
  const { result, events } = await run([
    frame("delta", { content: "fake " }) + frame("delta", { content: "assistant reply" }),
    frame("complete", { message_id: "row-1" }),
  ]);

  assert.equal(result.ok, true);
  assert.equal(result.ok && result.messageId, "row-1");
  assert.equal(result.ok && result.content, "fake assistant reply");
  assert.deepEqual(
    events.map((event) => event.kind),
    ["delta", "delta", "complete"],
  );
});

test("the request carries the session token and only the content", async () => {
  let seenUrl = "";
  let seenInit: RequestInit | undefined;
  await streamExecution({
    conversationId: CONVERSATION_ID,
    content: "Hello",
    accessToken: TOKEN,
    onEvent: () => {},
    fetchImpl: async (url, init) => {
      seenUrl = url;
      seenInit = init;
      return streamResponse([frame("complete", { message_id: "row-1" })]);
    },
  });

  assert.ok(seenUrl.endsWith(`/conversations/${CONVERSATION_ID}/execute/stream`));
  assert.equal(seenInit?.method, "POST");
  const headers = seenInit?.headers as Record<string, string>;
  assert.equal(headers.Authorization, `Bearer ${TOKEN}`);
  assert.equal(seenInit?.body, JSON.stringify({ content: "Hello" }));
});

test("an error event ends the stream as a failure", async () => {
  const { result } = await run([
    frame("delta", { content: "half an answer" }),
    frame("error", { code: "failed", message: "The agent run failed." }),
  ]);

  assert.equal(result.ok, false);
  assert.equal(!result.ok && result.message, "The agent run failed.");
});

test("a stream that ends without a completion is a failure", async () => {
  const { result } = await run([frame("delta", { content: "half" })]);

  assert.equal(result.ok, false);
  assert.equal(!result.ok && result.reason, "invalid-response");
});

test("a stream that never opens a body is a failure", async () => {
  const result = await streamExecution({
    conversationId: CONVERSATION_ID,
    content: "Hello",
    accessToken: TOKEN,
    onEvent: () => {},
    fetchImpl: async () => new Response(null, { status: 200 }),
  });

  assert.equal(result.ok, false);
  assert.equal(!result.ok && result.reason, "invalid-response");
});

test("an unauthenticated caller is reported without a request", async () => {
  let called = false;
  const result = await streamExecution({
    conversationId: CONVERSATION_ID,
    content: "Hello",
    accessToken: null,
    onEvent: () => {},
    fetchImpl: async () => {
      called = true;
      return streamResponse([]);
    },
  });

  assert.equal(called, false);
  assert.equal(result.ok, false);
  assert.equal(!result.ok && result.reason, "unauthenticated");
});

test("a rejected request is a network failure", async () => {
  const result = await streamExecution({
    conversationId: CONVERSATION_ID,
    content: "Hello",
    accessToken: TOKEN,
    onEvent: () => {},
    fetchImpl: async () => {
      throw new Error("offline");
    },
  });

  assert.equal(result.ok, false);
  assert.equal(!result.ok && result.reason, "network");
});

test("a pre-stream 404 is reported without opening a stream", async () => {
  const { result } = await run([], { ok: false, status: 404 });

  assert.equal(result.ok, false);
  assert.equal(!result.ok && result.reason, "not-found");
});

test("a pre-stream 401 is reported as unauthenticated", async () => {
  const { result } = await run([], { ok: false, status: 401 });

  assert.equal(result.ok, false);
  assert.equal(!result.ok && result.reason, "unauthenticated");
});

test("a pre-stream 422 is reported as invalid input", async () => {
  const { result } = await run([], { ok: false, status: 422 });

  assert.equal(result.ok, false);
  assert.equal(!result.ok && result.reason, "invalid-input");
});

test("a malformed event does not stop the ones after it", async () => {
  const { result } = await run([
    "event: delta\ndata: {broken\n\n" + frame("complete", { message_id: "row-9" }),
  ]);

  assert.equal(result.ok, true);
  assert.equal(result.ok && result.messageId, "row-9");
});
});

test("flush reads a trailing frame the server never terminated", () => {
  const parser = new ExecutionEventParser();
  assert.deepEqual(parser.push("event: delta\ndata: {\"content\":\"x\"}"), []);
  assert.deepEqual(parser.flush(), [{ kind: "delta", content: "x" }]);
});

test("flush with nothing left returns nothing", () => {
  const parser = new ExecutionEventParser();
  parser.push(frame("delta", { content: "x" }));
  assert.deepEqual(parser.flush(), []);
});