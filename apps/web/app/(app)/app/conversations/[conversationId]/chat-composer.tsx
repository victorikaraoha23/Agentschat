"use client";

import { useState, type FormEvent } from "react";

import styles from "./conversation.module.css";
import {
  draftAfterSubmit,
  initialComposerState,
  withComposerDraft,
  type ChatSubmitOutcome,
} from "@/lib/conversation-composer";
import { messageContentProblem } from "@/lib/messages-api";

export interface ChatComposerProps {
  /** True while a send is in flight; disables Send so nothing is sent twice. */
  submitting: boolean;
  /** Sends the content and reports what the API answered. */
  onSubmit: (content: string) => Promise<ChatSubmitOutcome>;
}

/**
 * The chat composer: a labelled message field and a real Send button.
 *
 * It owns only the draft. Sending is the page's job, because the page owns the
 * conversation id and the messages the conversation already holds; the outcome
 * comes back here so a stored message clears the field and a failed one leaves
 * the text in place.
 *
 * The client checks the draft before sending (empty, or over the documented
 * limit) purely so the user gets an answer immediately. The API re-checks
 * everything it accepts and stays the authority.
 */
export function ChatComposer({ submitting, onSubmit }: ChatComposerProps) {
  const [composer, setComposer] = useState(initialComposerState);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) {
      return;
    }
    const problem = messageContentProblem(composer.draft);
    if (problem !== null) {
      return;
    }
    const outcome = await onSubmit(composer.draft);
    setComposer((state) => draftAfterSubmit(state, outcome));
  }

  const problem = messageContentProblem(composer.draft);
  const sendDisabled = submitting || problem !== null;

  return (
    <form className={styles.composer} onSubmit={handleSubmit} noValidate>
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
        <button type="submit" disabled={sendDisabled} aria-busy={submitting}>
          {submitting ? "Sending…" : "Send"}
        </button>
      </div>
      <p className={styles.composerHint}>
        {problem !== null && !submitting
          ? problem
          : "Sent messages are saved to this conversation."}
      </p>
    </form>
  );
}