/**
 * Reading a streamed agent run from the API (Task 8.3).
 *
 * The conversation page shows the reply as it arrives, so this module owns two
 * things: parsing the server-sent event framing out of a response body that
 * arrives in arbitrary pieces, and turning one stream into typed events the page
 * can act on.
 *
 * The parser is deliberately specific and small. It knows this API's application event
 * names and nothing else, and it never guesses: an event it cannot read is
 * skipped rather than turned into content, because showing a half-read payload
 * would put something in the conversation that the server never said (root
 * `AGENTS.md` §13).
 *
 * One network chunk is not one event. Chunks split mid-line, mid-JSON, or
 * between the `event:` and `data:` lines, so bytes are buffered until a blank
 * line closes an event -- that is what makes the reader correct regardless of
 * how the network chose to split things.
 */

import { getAccessToken } from "./auth.ts";
import { API_BASE_URL } from "./api-base-url.ts";
import { isMessagePayload, toMessage, type Message } from "./messages-api.ts";

/** The event names the API sends. Nothing else is meaningful to this page. */
export type ExecutionStreamEvent =
  | { kind: "start"; message: Message }
  | { kind: "delta"; content: string }
  | { kind: "complete"; messageId: string; message: Message }
  | { kind: "error"; code: string; message: string };

/** Why a stream ended without a `complete` event. */
export type ExecutionStreamFailure =
  | "aborted"
  | "unauthenticated"
  | "forbidden"
  | "not-found"
  | "invalid-input"
  | "network"
  | "http"
  | "invalid-response"
  | "unexpected";

export type ExecutionStreamResult =
  | { ok: true; messageId: string; content: string; message: Message }
  | { ok: false; reason: ExecutionStreamFailure; message: string };

const SEPARATOR = "\n\n";

/**
 * Incremental Server-Sent Events reader.
 *
 * Feed it whatever text arrived; it returns the events that became complete.
 * State lives here rather than in the caller so the page never has to know that
 * a frame can span several chunks.
 */
export class ExecutionEventParser {
  private buffer = "";

  /** Append a chunk of decoded text and return every event it completed. */
  push(chunk: string): ExecutionStreamEvent[] {
    this.buffer += chunk;
    const events: ExecutionStreamEvent[] = [];
    let boundary = this.buffer.indexOf(SEPARATOR);
    while (boundary !== -1) {
      const frame = this.buffer.slice(0, boundary);
      this.buffer = this.buffer.slice(boundary + SEPARATOR.length);
      const parsed = parseFrame(frame);
      if (parsed !== null) {
        events.push(parsed);
      }
      boundary = this.buffer.indexOf(SEPARATOR);
    }
    return events;
  }

  /**
   * Read whatever is left once the response ends.
   *
   * A server that closes without a trailing blank line still sent a usable last
   * event, so it is not thrown away; the caller is what decides an unterminated
   * stream is a failure.
   */
  flush(): ExecutionStreamEvent[] {
    const remaining = this.buffer.trim();
    this.buffer = "";
    if (remaining === "") {
      return [];
    }
    const parsed = parseFrame(remaining);
    return parsed === null ? [] : [parsed];
  }
}

/** Read one frame's `event:`/`data:` lines into a typed event, or null. */
function parseFrame(frame: string): ExecutionStreamEvent | null {
  let name = "";
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith(":")) {
      // A comment, which the SSE format allows for keep-alives.
      continue;
    }
    if (line.startsWith("event:")) {
      name = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).replace(/^ /, ""));
    }
  }
  if (name === "" || dataLines.length === 0) {
    return null;
  }

  let payload: unknown;
  try {
    payload = JSON.parse(dataLines.join("\n"));
  } catch {

    // Unreadable JSON is not shown to anyone; the caller treats the missing
    // event as a failure rather than displaying a guessed payload.
    return null;
  }
  if (typeof payload !== "object" || payload === null) {
    return null;
  }
  const data = payload as Record<string, unknown>;

  if (name === "delta") {
    return typeof data.content === "string"
      ? { kind: "delta", content: data.content }
      : null;
  }
  if (name === "start") {
    return isMessagePayload(data.message) && data.message.role === "user"
      ? { kind: "start", message: toMessage(data.message) }
      : null;
  }
  if (name === "complete") {
    return isMessagePayload(data.message) && data.message.role === "assistant" &&
      data.message_id === data.message.id && data.content === data.message.content
      ? { kind: "complete", messageId: data.message_id, message: toMessage(data.message) }
      : null;
  }
  if (name === "error") {
    return typeof data.message === "string"
      ? { kind: "error", code: String(data.code ?? "unknown"), message: data.message }
      : null;
  }
  return null;
}


const SESSION_MESSAGE = "Your message could not be sent: sign in again.";
const REQUEST_FAILED_MESSAGE = "Request failed.";
const STREAM_BROKE_MESSAGE = "The reply stopped unexpectedly.";
const NO_COMPLETION_MESSAGE = "The agent did not finish its reply.";
const UNEXPECTED_RESPONSE_MESSAGE = "The API sent something unreadable.";

/** Wording for failures that arrive before the stream opens. */
const STATUS_MESSAGES: Record<number, string> = {
  401: SESSION_MESSAGE,
  403: "You do not have access to this conversation.",
  404: "That conversation could not be found.",
  422: "That message could not be sent.",
};

type FetchLike = (url: string, init?: RequestInit) => Promise<Response>;

export interface StreamExecutionOptions {
  conversationId: string;
  content: string;
  /** Called for each event as it arrives, in order. */
  onEvent: (event: ExecutionStreamEvent) => void;
  accessToken?: string | null;
  fetchImpl?: FetchLike;
  signal?: AbortSignal;
}

/**
 * Submit a message and consume the streamed reply.
 *
 * Resolves once the stream has ended, successfully or not. It never throws:
 * every outcome is a result, because a failure here is something the page has to
 * show rather than an exception it would have to catch.
 */
export async function streamExecution(
  options: StreamExecutionOptions,
): Promise<ExecutionStreamResult> {
  const token =
    options.accessToken !== undefined ? options.accessToken : await getAccessToken();
  if (token === null || token === "") {
    return { ok: false, reason: "unauthenticated", message: SESSION_MESSAGE };
  }

  const fetchImpl = options.fetchImpl ?? ((url, init) => fetch(url, init));
  const base = API_BASE_URL.replace(/\/+$/, "");
  const url = `${base}/conversations/${encodeURIComponent(options.conversationId)}/execute/stream`;

  let response: Response;
  try {
    response = await fetchImpl(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify({ content: options.content }),
      signal: options.signal,
    });
  } catch {
    return { ok: false, reason: "network", message: REQUEST_FAILED_MESSAGE };
  }

  // A failure before the stream opens is still an ordinary HTTP error.
  if (!response.ok) {
    return {
      ok: false,
      reason: failureForStatus(response.status),
      message: STATUS_MESSAGES[response.status] ?? "The agent could not be reached.",
    };
  }
  if (response.body === null) {
    return {
      ok: false,
      reason: "invalid-response",
      message: UNEXPECTED_RESPONSE_MESSAGE,
    };
  }

  const parser = new ExecutionEventParser();
  let completed: Message | null = null;
  let failure: string | null = null;

  const dispatch = (events: ExecutionStreamEvent[]): void => {
    for (const event of events) {
      if (options.signal?.aborted || completed !== null || failure !== null) {
        return;
      }
      options.onEvent(event);
      if (event.kind === "complete") {
        completed = event.message;
      } else if (event.kind === "error") {
        failure = event.message;
      }
    }
  };

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      dispatch(parser.push(decoder.decode(value, { stream: true })));
    }
    dispatch(parser.flush());
  } catch {
    // The connection dropped mid-stream. Whatever arrived is still shown, but a
    // stream that broke is not a completed reply.
    return { ok: false, reason: "network", message: STREAM_BROKE_MESSAGE };
  } finally {
    reader.releaseLock();
  }

  if (options.signal?.aborted) {
    return { ok: false, reason: "aborted", message: "" };
  }
  if (completed !== null) {
    const message: Message = completed;
    return { ok: true, messageId: message.id, content: message.content, message };
  }
  if (failure !== null) {
    return { ok: false, reason: "http", message: failure };
  }
  return { ok: false, reason: "invalid-response", message: NO_COMPLETION_MESSAGE };
}

/** Map a pre-stream HTTP status onto the page's failure vocabulary. */
function failureForStatus(status: number): ExecutionStreamFailure {
  if (status === 401) {
    return "unauthenticated";
  }
  if (status === 403) {
    return "forbidden";
  }
  if (status === 404) {
    return "not-found";
  }
  if (status === 422) {
    return "invalid-input";
  }
  return "http";
}
