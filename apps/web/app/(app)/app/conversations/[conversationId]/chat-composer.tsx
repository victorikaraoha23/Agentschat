"use client";

import { useState, type FormEvent } from "react";

import styles from "./conversation.module.css";
import {
  canSendDraft,
  COMPOSER_NOTICE_MESSAGE,
  initialComposerState,
  submitComposerDraft,
  withComposerDraft,
} from "@/lib/conversation-composer";

/**
 * The chat composer: a labelled message field and a real Send button.
 *
 * Task 6.1 persists nothing, so this composes no request at all. Submitting is
 * handled by `lib/conversation-composer.ts`, which shows an honest notice and
 * keeps what was typed — no message is stored, no assistant replies, and no
 * network call is made. The button is disabled while the draft holds no text so
 * the control's state is communicated, and the notice is announced through a
 * status region when it appears.
 */
export function ChatComposer() {
  const [composer, setComposer] = useState(initialComposerState);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    // Nothing is sent in this task; prevent the form's default navigation so the
    // notice below is the only result of submitting.
    event.preventDefault();
    setComposer((state) => submitComposerDraft(state));
  }

  return (
    <form className={styles.composer} onSubmit={handleSubmit}>
      <label className={styles.composerLabel} htmlFor="conversation-message">
        Message
      </label>
      <div className={styles.composerRow}>
        <textarea
          className={styles.composerInput}
          id="conversation-message"
          name="message"
          rows={1}
          placeholder="Type your message"
          value={composer.draft}
          onChange={(event) =>
            setComposer((state) => withComposerDraft(state, event.target.value))
          }
        />
        <button type="submit" disabled={!canSendDraft(composer.draft)}>
          Send
        </button>
      </div>
      {composer.noticeVisible && (
        <p className={`muted ${styles.composerNotice}`} role="status">
          {COMPOSER_NOTICE_MESSAGE}
        </p>
      )}
    </form>
  );
}
