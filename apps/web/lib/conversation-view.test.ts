/**
 * Unit tests for the conversation page's view decision (Task 6.1).
 *
 * `toConversationPageView` and `conversationTitle` are pure functions of the
 * session state and the typed API outcome, so these tests need no browser, no
 * Supabase, and no network — only the mapping the page renders.
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import type { SessionState } from "./auth.ts";
import {
  conversationTitle,
  toConversationPageView,
  UNTITLED_CONVERSATION,
} from "./conversation-view.ts";
import type {
  Conversation,
  ConversationFailureReason,
  ConversationResult,
} from "./conversations-api.ts";

const AUTHENTICATED: SessionState = {
  status: "authenticated",
  userId: "user-1",
  email: "person@example.com",
};

function conversation(overrides: Partial<Conversation> = {}): Conversation {
  return {
    id: "conversation-1",
    userId: "user-1",
    title: "Trip planning",
    createdAt: "2026-10-01T10:00:00Z",
    updatedAt: "2026-10-02T12:00:00Z",
    ...overrides,
  };
}

/** A typed failure outcome, shaped exactly as `getConversation` returns it. */
function failure(reason: ConversationFailureReason, message: string): ConversationResult {
  return { ok: false, reason, message };
}

test("a resolving session shows the loading view, whatever the API reported", () => {
  const loaded = toConversationPageView(null, {
    ok: true,
    conversation: conversation(),
  });
  assert.deepEqual(loaded, { view: "loading" });
});

test("an unauthenticated session is denied before anything is loaded", () => {
  const view = toConversationPageView({ status: "unauthenticated" }, null);
  assert.deepEqual(view, { view: "denied", reason: "unauthenticated" });
});

test("an unconfigured backend is denied as unconfigured", () => {
  const view = toConversationPageView({ status: "unconfigured" }, null);
  assert.deepEqual(view, { view: "denied", reason: "unconfigured" });
});

test("an unreadable session is denied as unreadable, never granted", () => {
  const session: SessionState = {
    status: "error",
    message: "Your session could not be read: sign in again.",
  };
  assert.deepEqual(toConversationPageView(session, null), {
    view: "denied",
    reason: "unreadable",
  });
});

test("an authenticated session with no answer yet shows the loading view", () => {
  assert.deepEqual(toConversationPageView(AUTHENTICATED, null), { view: "loading" });
});

test("a loaded conversation shows the ready workspace", () => {
  const loaded = conversation({ title: "Trip planning" });
  assert.deepEqual(toConversationPageView(AUTHENTICATED, { ok: true, conversation: loaded }), {
    view: "ready",
    conversation: loaded,
  });
});

test("a conversation that does not exist shows the not-found view", () => {
  const view = toConversationPageView(
    AUTHENTICATED,
    failure("not-found", "That conversation could not be found."),
  );
  assert.deepEqual(view, { view: "not-found" });
});

test("a conversation owned by someone else is indistinguishable from a missing one", () => {
  // The API answers both with `not-found`; the page must not treat them
  // differently either.
  const foreign = toConversationPageView(
    AUTHENTICATED,
    failure("not-found", "That conversation could not be found."),
  );
  const malformedId = toConversationPageView(
    AUTHENTICATED,
    failure("invalid-input", "That conversation id is not valid."),
  );
  assert.deepEqual(foreign, malformedId);
});

test("a rejected session shows the sign-in denial instead of a retry loop", () => {
  const view = toConversationPageView(
    AUTHENTICATED,
    failure("unauthenticated", "Your conversation could not be loaded: sign in again."),
  );
  assert.deepEqual(view, { view: "denied", reason: "rejected" });
});

test("a network failure shows a recoverable error carrying the module's message", () => {
  const view = toConversationPageView(AUTHENTICATED, failure("network", "Request failed."));
  assert.deepEqual(view, { view: "error", message: "Request failed." });
});

test("a timeout shows the API module's timeout message", () => {
  const view = toConversationPageView(
    AUTHENTICATED,
    failure("network", "Loading your conversation timed out."),
  );
  assert.deepEqual(view, { view: "error", message: "Loading your conversation timed out." });
});

test("a non-success status shows an error reported by status code only", () => {
  const view = toConversationPageView(
    AUTHENTICATED,
    failure("http", "The API responded with HTTP 500."),
  );
  assert.deepEqual(view, { view: "error", message: "The API responded with HTTP 500." });
});

test("an unusable response body shows an error", () => {
  const view = toConversationPageView(
    AUTHENTICATED,
    failure("invalid-response", "The API response did not contain a conversation."),
  );
  assert.deepEqual(view, { view: "error", message: "The API response did not contain a conversation." });
});

test("an unexpected failure shows an error", () => {
  const view = toConversationPageView(
    AUTHENTICATED,
    failure(
      "unexpected",
      "An unexpected error occurred while loading your conversation.",
    ),
  );
  assert.deepEqual(view, {
    view: "error",
    message: "An unexpected error occurred while loading your conversation.",
  });
});

test("a titled conversation shows its title", () => {
  assert.equal(conversationTitle(conversation({ title: "Trip planning" })), "Trip planning");
});

test("a conversation with no title falls back, so the heading is never empty", () => {
  assert.equal(conversationTitle(conversation({ title: null })), UNTITLED_CONVERSATION);
  assert.equal(conversationTitle(conversation({ title: "" })), UNTITLED_CONVERSATION);
  assert.equal(conversationTitle(conversation({ title: "   " })), UNTITLED_CONVERSATION);
});

test("a surrounding-whitespace title is trimmed for display", () => {
  assert.equal(conversationTitle(conversation({ title: "  Trip planning  " })), "Trip planning");
});
