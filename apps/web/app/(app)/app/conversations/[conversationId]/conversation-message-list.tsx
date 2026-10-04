import styles from "./conversation.module.css";
import type { Message } from "@/lib/messages-api";

export interface ConversationMessageListProps {
  /** Confirmed messages, oldest first. */
  messages: Message[];
}

/**
 * The persisted messages in a conversation (Task 6.2).
 *
 * Deliberately plain: each message is its own block with its text and the time
 * the database recorded. Content is rendered as text by React, never as markup,
 * so a message can not introduce formatting or script into the page. Assistant
 * replies, tool output, streaming, and markdown arrive with the agent tasks and
 * are not stubbed here.
 */
export function ConversationMessageList({ messages }: ConversationMessageListProps) {
  return (
    <ol className={styles.messageList}>
      {messages.map((message) => (
        <li key={message.id} className={styles.message}>
          <p className={styles.messageMeta}>
            <span className={styles.messageAuthor}>You</span>
            <time dateTime={message.createdAt} className={styles.messageTime}>
              {formatMessageTime(message.createdAt)}
            </time>
          </p>
          <p className={styles.messageContent}>{message.content}</p>
        </li>
      ))}
    </ol>
  );
}

/**
 * Render a stored timestamp for a human, in the browser's own locale and time
 * zone, with the exact value kept on the `<time>` element for machines.
 */
function formatMessageTime(isoTimestamp: string): string {
  const parsed = new Date(isoTimestamp);
  return Number.isNaN(parsed.getTime()) ? "" : parsed.toLocaleTimeString();
}