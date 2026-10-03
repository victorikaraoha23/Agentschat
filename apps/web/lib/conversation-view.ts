/**
 * View decision for the conversation page (Task 6.1).
 *
 * A pure function of two things the page already has: the `SessionState` that
 * `lib/auth.ts` reports and the typed outcome of `GET /conversations/{id}` from
 * `lib/conversations-api.ts`. It maps them to the single view the page renders
 * — loading, a session denial, the safe not-found state, a recoverable failure,
 * or the ready workspace.
 *
 * Keeping the decision here means the component owns no authentication judgment
 * and no error classification of its own: it composes the existing session
 * boundary (`toShellAccess`) and the typed API result, and every state is
 * testable without a browser, Supabase, or a network call.
 *
 * Failure mapping is deliberate. `not-found` and `invalid-input` both become the
 * same not-found view, so a conversation that does not exist, one owned by
 * someone else, and a malformed id are indistinguishable — existence is never
 * revealed. A rejected session becomes the established "sign in again" denial
 * rather than a retry loop. Everything else keeps the module's own fixed message,
 * which is safe to show: no status line, body, or raw error object reaches here.
 */

import type { SessionState } from "./auth.ts";
import type { Conversation, ConversationResult } from "./conversations-api.ts";
import { toShellAccess } from "./shell-access.ts";

/** Shown when a conversation has no title, so the heading is never empty. */
export const UNTITLED_CONVERSATION = "Untitled conversation";

/**
 * Why the page is not showing the conversation.
 *
 * `unauthenticated`, `unconfigured`, and `unreadable` come from the session
 * boundary. `rejected` means the session looked valid but the API refused the
 * token — the same "sign in again" outcome from a different cause.
 */
export type ConversationPageDeniedReason =
  | "unauthenticated"
  | "unconfigured"
  | "unreadable"
  | "rejected";

/** The one view the conversation page renders. */
export type ConversationPageView =
  | { view: "loading" }
  | { view: "denied"; reason: ConversationPageDeniedReason }
  | { view: "not-found" }
  | { view: "error"; message: string }
  | { view: "ready"; conversation: Conversation };

/**
 * Decide which view the conversation page shows.
 *
 * - no session yet → loading, so no private content renders early;
 * - a denied session → the same denial the application shell shows;
 * - no API outcome yet → loading;
 * - a loaded conversation → ready, carrying the conversation;
 * - `not-found` / `invalid-input` → the one safe not-found view;
 * - `unauthenticated` → the sign-in denial;
 * - `network` / `http` / `invalid-response` / `unexpected` → a recoverable error
 *   carrying the message the API module produced.
 */
export function toConversationPageView(
  session: SessionState | null,
  result: ConversationResult | null,
): ConversationPageView {
  const access = toShellAccess(session);
  if (access.view === "loading") {
    return { view: "loading" };
  }
  if (access.view === "denied") {
    return { view: "denied", reason: access.reason };
  }

  // Granted session: the conversation load is the only thing left to decide.
  if (result === null) {
    return { view: "loading" };
  }
  if (result.ok) {
    return { view: "ready", conversation: result.conversation };
  }
  if (result.reason === "unauthenticated") {
    return { view: "denied", reason: "rejected" };
  }
  if (result.reason === "not-found" || result.reason === "invalid-input") {
    return { view: "not-found" };
  }
  return { view: "error", message: result.message };
}

/**
 * The conversation's title for display.
 *
 * The API stores a title as `NULL` when it is empty, and the page still needs a
 * heading in that case, so an absent or blank title falls back to
 * `UNTITLED_CONVERSATION`.
 */
export function conversationTitle(conversation: Conversation): string {
  const title = conversation.title?.trim() ?? "";
  return title === "" ? UNTITLED_CONVERSATION : title;
}
