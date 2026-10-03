import { ConversationPage } from "./conversation-page";

/**
 * The conversation workspace route: `/app/conversations/[conversationId]`.
 *
 * A server component that resolves the dynamic segment and hands the id to the
 * client page, which gates access through the existing session boundary and
 * loads the conversation through `lib/conversations-api.ts`. Only the id comes
 * from the URL: the page never accepts an owner, a role, or any other ownership
 * information from the route or from client state — the API decides ownership
 * from the verified token (root `AGENTS.md` §9).
 */
export default async function ConversationRoute({
  params,
}: PageProps<"/app/conversations/[conversationId]">) {
  const { conversationId } = await params;
  return <ConversationPage conversationId={conversationId} />;
}
