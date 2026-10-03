/**
 * Unit tests for the chat composer's rules (Task 6.1).
 *
 * The composer's state changes are pure functions, so these tests cover typing,
 * the Send gate, and what submitting does — without a browser and without any
 * way for a test to make a request.
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  canSendDraft,
  COMPOSER_NOTICE_MESSAGE,
  initialComposerState,
  submitComposerDraft,
  withComposerDraft,
} from "./conversation-composer.ts";

test("the composer starts empty, with no notice", () => {
  assert.deepEqual(initialComposerState(), { draft: "", noticeVisible: false });
});

test("typing keeps what the user typed", () => {
  const typed = withComposerDraft(initialComposerState(), "Plan a trip to Lisbon");
  assert.deepEqual(typed, { draft: "Plan a trip to Lisbon", noticeVisible: false });
});

test("send is available only for a draft that contains text", () => {
  assert.equal(canSendDraft(""), false);
  assert.equal(canSendDraft("   "), false);
  assert.equal(canSendDraft("\n\t "), false);
  assert.equal(canSendDraft("Hi"), true);
  assert.equal(canSendDraft("  Hi  "), true);
});

test("the send control is disabled until the draft contains text", () => {
  // The component renders `disabled={!canSendDraft(draft)}`; this pins the rule
  // that makes the disabled state correct.
  assert.equal(canSendDraft(initialComposerState().draft), false);
  assert.equal(canSendDraft(withComposerDraft(initialComposerState(), "Hi").draft), true);
});

test("submitting shows the notice and keeps the draft, because nothing was sent", () => {
  const typed = withComposerDraft(initialComposerState(), "Plan a trip");
  const submitted = submitComposerDraft(typed);
  assert.deepEqual(submitted, { draft: "Plan a trip", noticeVisible: true });
});

test("submitting an empty draft changes nothing", () => {
  const empty = initialComposerState();
  assert.deepEqual(submitComposerDraft(empty), empty);
});

test("typing again hides a notice that belonged to the previous text", () => {
  const submitted = submitComposerDraft(
    withComposerDraft(initialComposerState(), "Plan a trip"),
  );
  assert.deepEqual(withComposerDraft(submitted, "Plan a trip to Lisbon"), {
    draft: "Plan a trip to Lisbon",
    noticeVisible: false,
  });
});

test("the notice states that messages are not sent yet", () => {
  assert.match(COMPOSER_NOTICE_MESSAGE, /not sent/i);
});
