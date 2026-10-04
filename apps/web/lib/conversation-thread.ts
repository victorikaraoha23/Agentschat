/**
 * Conversation thread state for the conversation page (Task 6.2).
 *
 * The page shows the messages this conversation actually holds, and this module
 * is where every change to that list happens: a submit starts, the API confirms
 * one message, or the attempt fails. Keeping the transitions pure means the
 * rules that matter — a second submit cannot start while one is in flight, and
 * only a confirmed message is ever shown — are testable without a browser.
 *
 * The server is authoritative: a message is appended because the API returned
 * it, never because the user pressed Send, and a failed attempt adds nothing.
 */

import type { Message } from "./messages-api.ts";

/** Everything the page renders about the conversation's messages. */
export interface ConversationThreadState {
  /** Confirmed messages, oldest first — the order they were sent. */
  messages: Message[];
  /** Whether a send is in flight, which is what disables the Send control. */
  submitting: boolean;
  /** The message to show for a failed attempt, or `null` when there is none. */
  error: string | null;
}

/** The state a freshly opened conversation starts from. */
export function initialThreadState(): ConversationThreadState {
  return { messages: [], submitting: false, error: null };
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
  return { ...state, submitting: true, error: null };
}

/**
 * Append a message the API confirmed, and end the submission.
 *
 * The previous error is dropped: the conversation now shows a message that was
 * really stored, so the failure state no longer describes what the user sees.
 */
export function messageSubmitted(
  state: ConversationThreadState,
  message: Message,
): ConversationThreadState {
  return {
    messages: [...state.messages, message],
    submitting: false,
    error: null,
  };
}

/**
 * Record a failed attempt and end the submission.
 *
 * Nothing is appended and the list is untouched: the message was not stored, so
 * the conversation must not pretend otherwise. The composer keeps the typed text
 * for the same reason.
 */
export function messageSubmitFailed(
  state: ConversationThreadState,
  message: string,
): ConversationThreadState {
  return { ...state, submitting: false, error: message };
}
