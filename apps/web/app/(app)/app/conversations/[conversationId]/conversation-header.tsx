import Link from "next/link";

import styles from "./conversation.module.css";

export interface ConversationHeaderProps {
  /** The conversation title; the caller applies the untitled fallback. */
  title: string;
}

/**
 * The conversation header: the conversation's title as the page heading, plus a
 * way back to the authenticated application area.
 *
 * Deliberately minimal (Task 6.1): rename, delete, agent, model, tool, settings,
 * sharing, and collaboration controls belong to later tasks, and the
 * conversation list belongs to the navigation work — none of it is stubbed here.
 */
export function ConversationHeader({ title }: ConversationHeaderProps) {
  return (
    <header className={`${styles.header} surface`}>
      <h1 className={styles.title}>{title}</h1>
      <Link href="/app">Back to the app</Link>
    </header>
  );
}
