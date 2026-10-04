/**
 * Composer rules for the conversation page (Task 6.2).
 *
 * The composer owns one thing: the text the user has typed. Everything about
 * sending is a rule in this file, so the important behaviour is testable
 * without a browser:
 *
 * - Send is available only for a draft with actual text.
 * - A **successful** submit clears the draft, because the message is stored and
 *   the next one should start fresh.
 * - A **failed** submit keeps the draft. Nothing was stored, so throwing the
 *   text away would lose work and imply a delivery that never happened
 *   (root `AGENTS.md` §13: never report success for an unknown outcome).
 *
 * The request itself belongs to the page, which owns the conversation id and the
 * thread state; this module makes no request and knows nothing about the API.
 */

/** What the composer renders: the text so far. */
export interface ComposerState {
  /** What the user has typed, exactly as typed. */
  draft: string;
}

/** What a submit attempt reports back to the composer. */
export interface ChatSubmitOutcome {
  /** Whether the API confirmed the message. */
  ok: boolean;
  /** Message to show when it did not; empty when it did. */
  message: string;
}

/** The state a freshly mounted composer starts from. */
export function initialComposerState(): ComposerState {
  return { draft: "" };
}

/**
 * Whether Send is available: only for a draft that contains text.
 *
 * Whitespace alone is not something to send, so the button stays disabled while
 * the draft is effectively empty.
 */
export function canSendDraft(draft: string): boolean {
  return draft.trim().length > 0;
}

/** Typing updates the draft and nothing else. */
export function withComposerDraft(state: ComposerState, draft: string): ComposerState {
  return { draft };
}

/**
 * Apply the result of a submit to the draft.
 *
 * A confirmed message clears the field; a failed attempt leaves the text
 * exactly where it was, ready to be sent again.
 */
export function draftAfterSubmit(
  state: ComposerState,
  outcome: ChatSubmitOutcome,
): ComposerState {
  return outcome.ok ? initialComposerState() : state;
}