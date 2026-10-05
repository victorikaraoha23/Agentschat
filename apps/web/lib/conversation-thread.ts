/**
 * Conversation thread state for the conversation page (Tasks 6.2 and 8.3).
 *
 * The page shows the messages this conversation actually holds, and this module
 * is where every change to that list happens: a send starts, the API confirms
 * one message, a streamed reply grows, it completes, or the attempt fails.
 * Keeping the transitions pure means the rules that matter -- a second send
 * cannot start while one is in flight, and only a confirmed message is ever
 * shown -- are testable without a browser.
 *
 * The server is authoritative: a message is appended because the API returned
 * it, never because the user pressed Send, and a failed attempt adds nothing.
 */

import type { Message } from "./messages-api.ts";

/** Where a send has got to, which is what the page renders around the reply. */
export type StreamStatus = "idle" | "streaming" | "completed" | "error";

/** Everything the page renders about the conversation's messages. */
export interface ConversationThreadState {
  /** Confirmed messages, oldest first -- the order they were sent. */
  messages: Message[];
  /** Whether a send is in flight, which is what disables the Send control. */
  submitting: boolean;
  /** The message to show for a failed attempt, or `null` when there is none. */
  error: string | null;
  /** How the current attempt is going. */
  streamStatus: StreamStatus;
  /**
   * The reply as it has arrived so far.
   *
   * Empty unless a reply is streaming or has just finished, and never merged
   * into `messages`: while it is incomplete it is not something the server
   * stored, and a run that fails must not leave a half answer in the thread.
   */
  streamingContent: string;
}

/** The state a freshly opened conversation starts from. */
export function initialThreadState(): ConversationThreadState {
  return {
    messages: [],
    submitting: false,
    error: null,
    streamStatus: "idle",
    streamingContent: "",
  };
}

/**
 * Mark a submission as started.
 *
 * A submit requested while one is already in flight is ignored: that is what
 * prevents a double click, an impatient Enter, or a retried request from sending
 * the same message twice.
 */
export function beginMessageSubmit(state: ConversationThreadState): ConversationThreadState {
  if (state.submitting) {
    return state;
  }
  return {
    ...state,
    submitting: true,
    error: null,
    streamStatus: "streaming",
    streamingContent: "",
  };
}

/** Record the confirmed user message while the assistant is still running. */
export function streamStarted(
  state: ConversationThreadState,
  message: Message,
): ConversationThreadState {
  return { ...state, messages: [...state.messages, message] };
}

/** Append streamed text to the reply being shown. */
export function streamDelta(
  state: ConversationThreadState,
  content: string,
): ConversationThreadState {
  return { ...state, streamingContent: state.streamingContent + content };
}

/**
 * Replace the provisional reply with the message the server actually stored.
 *
 * The API's row is what the thread gains, not the accumulated text: the two are
 * the same content, but the row is what a later reload will show, and it carries
 * the id and timestamp. The provisional text is cleared because it now has a
 * permanent home in the list.
 */
export function streamCompleted(
  state: ConversationThreadState,
  message: Message,
): ConversationThreadState {
  return {
    messages: [...state.messages, message],
    submitting: false,
    error: null,
    streamStatus: "completed",
    streamingContent: "",
  };
}

/**
 * End a stream that failed after it started.
 *
 * Any text that arrived is dropped along with the attempt: it was never stored,
 * and keeping it in the thread would show an unfinished answer as though the
 * agent had said it (root `AGENTS.md` §10).
 */
export function streamFailed(
  state: ConversationThreadState,
  message: string,
): ConversationThreadState {
  return {
    ...state,
    submitting: false,
    error: message,
    streamStatus: "error",
    streamingContent: "",
  };
}
