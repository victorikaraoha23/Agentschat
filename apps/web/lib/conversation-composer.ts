/**
 * Composer state for the conversation page (Task 6.1).
 *
 * The composer accepts typing, but nothing is sent: messages are not persisted
 * until the next task, so submitting must not pretend otherwise. These pure
 * functions are the entire rule set — what makes Send available, and what a
 * submit does (show an honest notice and keep the draft, because nothing was
 * delivered). There is no request here or in the component, so there is no fake
 * API call to make, and clearing the input after a "send" is deliberately
 * avoided: it would report a success that did not happen (root `AGENTS.md` §13).
 */

/** What the notice says when someone submits before messaging exists. */
export const COMPOSER_NOTICE_MESSAGE =
  "Messages are not sent yet — saving messages arrives with the next update.";

/** Everything the composer renders, with nothing derived in the component. */
export interface ComposerState {
  /** What the user has typed; never sent, and never cleared by a submit. */
  draft: string;
  /** Whether the not-yet-sent notice is on screen. */
  noticeVisible: boolean;
}

/** The state a freshly mounted composer starts from. */
export function initialComposerState(): ComposerState {
  return { draft: "", noticeVisible: false };
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

/** Typing updates the draft and hides a notice that belonged to earlier text. */
export function withComposerDraft(state: ComposerState, draft: string): ComposerState {
  return { draft, noticeVisible: false };
}

/**
 * Submitting the draft shows the notice instead of sending, and keeps the draft.
 *
 * An empty draft is a no-op, so the rule holds even if the disabled button is
 * activated by keyboard or assistive technology.
 */
export function submitComposerDraft(state: ComposerState): ComposerState {
  if (!canSendDraft(state.draft)) {
    return state;
  }
  return { ...state, noticeVisible: true };
}
