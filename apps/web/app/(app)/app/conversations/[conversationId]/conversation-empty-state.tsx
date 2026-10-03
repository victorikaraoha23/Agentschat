import styles from "./conversation.module.css";

/**
 * The empty state of the message area (Task 6.1).
 *
 * The conversation has no messages yet because none can be sent yet. This says
 * so plainly: no sample conversation, no simulated assistant reply, and no
 * invented history. Task 6.2 replaces it with the real message list when
 * persistence exists.
 */
export function ConversationEmptyState() {
  return (
    <div className={styles.empty}>
      <h2 className={styles.emptyTitle}>No messages yet</h2>
      <p className="muted">Ready for input. Messages will appear here once sending is connected.</p>
    </div>
  );
}
