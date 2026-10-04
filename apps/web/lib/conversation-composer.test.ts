/**
 * Unit tests for the chat composer's rules (Task 6.2).
 *
 * Typing, the Send gate, and what a submit does to the draft are pure
 * functions, so these tests cover the composer's behaviour with no browser and
 * no way for a test to make a request.
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  canSendDraft,
  draftAfterSubmit,
  initialComposerState,
  withComposerDraft,
  type ChatSubmitOutcome,
} from "./conversation-composer.ts";

const SENT: ChatSubmitOutcome = { ok: true, message: "" };
const FAILED: ChatSubmitOutcome = { ok: false, message: "Request failed." };

test("the composer starts empty", () => {
  assert.deepEqual(initialComposerState(), { draft: "" });
});

test("typing keeps what the user typed", () => {
  assert.deepEqual(withComposerDraft(initialComposerState(), "Plan a trip"), {
    draft: "Plan a trip",
  });
});

test("typing replaces the previous text rather than appending to it", () => {
  const typed = withComposerDraft(initialComposerState(), "Plan a trip");

  assert.deepEqual(withComposerDraft(typed, "Plan a trip to Lisbon"), {
    draft: "Plan a trip to Lisbon",
  });
});

test("send is available only for a draft that contains text", () => {
  assert.equal(canSendDraft(""), false);
  assert.equal(canSendDraft("   "), false);
  assert.equal(canSendDraft("\n\t "), false);
  assert.equal(canSendDraft("Hi"), true);
  assert.equal(canSendDraft("  Hi  "), true);
});

test("a submitted message clears the draft, because it was stored", () => {
  const typed = withComposerDraft(initialComposerState(), "Plan a trip");

  assert.deepEqual(draftAfterSubmit(typed, SENT), { draft: "" });
});

test("a failed submit keeps the draft, because nothing was stored", () => {
  const typed = withComposerDraft(initialComposerState(), "Plan a trip");

  assert.deepEqual(draftAfterSubmit(typed, FAILED), { draft: "Plan a trip" });
});

test("a retry after a failure starts from the same text", () => {
  const typed = withComposerDraft(initialComposerState(), "Plan a trip");

  const afterFailure = draftAfterSubmit(typed, FAILED);

  assert.equal(draftAfterSubmit(afterFailure, SENT).draft, "");
  assert.equal(afterFailure.draft, typed.draft);
});