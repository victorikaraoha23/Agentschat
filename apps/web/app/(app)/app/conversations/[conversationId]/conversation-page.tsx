"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ChatComposer } from "./chat-composer";
import styles from "./conversation.module.css";
import { ConversationEmptyState } from "./conversation-empty-state";
import { ConversationHeader } from "./conversation-header";
import { getCurrentSession, type SessionState } from "@/lib/auth";
import type {
  ConversationPageDeniedReason,
  ConversationPageView,
} from "@/lib/conversation-view";
import { conversationTitle, toConversationPageView } from "@/lib/conversation-view";
import { getConversation, type ConversationResult } from "@/lib/conversations-api";
import { createMessage } from "@/lib/messages-api";
import { toShellAccess } from "@/lib/shell-access";

const DENIED_MESSAGES: Record<ConversationPageDeniedReason, string> = {
  unauthenticated: "Sign in to open this conversation.",
  unconfigured: "Authentication is not configured, so conversations are unavailable.",
  unreadable: "Your session could not be read: sign in again.",
  rejected: "Your conversation could not be loaded: sign in again.",
};

const LOADING_MESSAGE = "Loading conversation…";
const NOT_FOUND_MESSAGE = "That conversation could not be found.";
const NOT_FOUND_TITLE = "Conversation not found";
const ERROR_TITLE = "Conversation unavailable";
const BACK_LINK_LABEL = "Back to the app";
const RETRY_LABEL = "Try again";

export interface ConversationPageProps {
  /** The id from the route. The API, not this component, decides ownership. */
  conversationId: string;
}

/**
 * The conversation page body: session gate, conversation load, the messages it
 * holds, and sending a new one (Task 6.2).
 *
 * Access uses the same boundary as the rest of the application -- the session
 * `lib/auth.ts` reports, mapped through `toShellAccess` -- so there is no second
 * authentication system and no private content renders before a session is
 * granted. The conversation is read and written with the typed functions in
 * `lib/conversations-api.ts` and `lib/messages-api.ts`, which carry the
 * session's access token; nothing here renders an owner id, a token, or a raw
 * failure.
 *
 * A message is shown only after the API confirms it was stored, so the
 * conversation never contains something that does not exist. This task stops at
 * persistence: no agent runs, no reply is produced, and nothing is streamed.
 */
export function ConversationPage({ conversationId }: ConversationPageProps) {
  const [session, setSession] = useState<SessionState | null>(null);
  // The loaded result is tagged with the id and the attempt it belongs to, so
  // navigating to another conversation — or retrying — never shows the previous
  // conversation's answer while the new one is in flight.
  const [load, setLoad] = useState<{
    conversationId: string;
    attempt: number;
    result: ConversationResult;
  } | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [thread, setThread] = useState<ConversationThreadState>(initialThreadState);

  useEffect(() => {
    let userId: string | null = null;
    return subscribeToSession((next) => {
      const nextUserId = next.status === "authenticated" ? next.userId : null;
      if (nextUserId !== userId) {
        userId = nextUserId;
        setLoad(null);
        // Also invalidate in-flight results, including a quick sign-out/sign-in
        // to the same account before React has cleaned up the previous effect.
        setAttempt((current) => current + 1);
      }
      setSession(next);
    });
  }, []);

  const access = toShellAccess(session);

  useEffect(() => {
    if (access.view !== "granted") {
      return;
    }
    let cancelled = false;
    void getConversation({ conversationId }).then((result) => {
      if (!cancelled) {
        setLoad({ conversationId, attempt, result });
      }
    });
    return () => {
      cancelled = true;
    };
  }, [conversationId, access.view, attempt]);

  const retry = useCallback(() => {
    setAttempt((current) => current + 1);
  }, []);

  const sendMessage = useCallback(
    async (content: string): Promise<ChatSubmitOutcome> => {
      // The thread rules refuse a second submit while one is in flight, so a
      // double click or an impatient Enter cannot send the same text twice.
      setThread(beginMessageSubmit);
      const result = await createMessage({ conversationId, content });
      if (result.ok) {
        setThread((state) => messageSubmitted(state, result.message));
        return { ok: true, message: "" };
      }
      setThread((state) => messageSubmitFailed(state, result.message));
      return { ok: false, message: result.message };
    },
    [conversationId],
  );

  const result =
    load !== null && load.conversationId === conversationId && load.attempt === attempt
      ? load.result
      : null;
  const view: ConversationPageView = toConversationPageView(session, result);

  if (view.view === "denied") {
    return (
      <main className={styles.workspace}>
        <div className={styles.state}>
          <h1 className={styles.stateTitle}>Sign-in required</h1>
          <p className="status-error" role="alert">
            {DENIED_MESSAGES[view.reason]}
          </p>
          <p className="muted">
            <Link href="/login">Sign in</Link> or <Link href="/app">{BACK_LINK_LABEL}</Link>.
          </p>
        </div>
      </main>
    );
  }

  if (view.view === "not-found") {
    return (
      <main className={styles.workspace}>
        <div className={styles.state}>
          <h1 className={styles.stateTitle}>{NOT_FOUND_TITLE}</h1>
          <p className="status-error" role="alert">
            {NOT_FOUND_MESSAGE}
          </p>
          <p className="muted">
            <Link href="/app">{BACK_LINK_LABEL}</Link>
          </p>
        </div>
      </main>
    );
  }

  if (view.view === "error") {
    return (
      <main className={styles.workspace}>
        <div className={styles.state}>
          <h1 className={styles.stateTitle}>{ERROR_TITLE}</h1>
          <p className="status-error" role="alert">
            {view.message}
          </p>
          <div className={styles.stateActions}>
            <button type="button" onClick={retry}>
              {RETRY_LABEL}
            </button>
            <Link href="/app">{BACK_LINK_LABEL}</Link>
          </div>
        </div>
      </main>
    );
  }

  if (view.view === "loading") {
    // The same frame the ready workspace uses, so the page does not jump when
    // the conversation arrives.
    return (
      <main className={styles.workspace}>
        <div className={styles.state}>
          <p className="status-line" aria-live="polite">
            <span className="status-pending">{LOADING_MESSAGE}</span>
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className={styles.workspace}>
      <ConversationHeader title={conversationTitle(view.conversation)} />
      <section className={`${styles.messageArea} surface`} aria-label="Messages">
        {thread.messages.length === 0 ? (
          <ConversationEmptyState />
        ) : (
          <ConversationMessageList messages={thread.messages} />
        )}
      </section>
      <ChatComposer submitting={thread.submitting} onSubmit={sendMessage} />
      {thread.error !== null && (
        <p className="status-error" role="alert">
          {thread.error}
        </p>
      )}
    </main>
  );
}